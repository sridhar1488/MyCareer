from collections import defaultdict
from datetime import date, datetime, timedelta
from io import BytesIO
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from defusedxml.common import DefusedXmlException
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils.exceptions import InvalidFileException
from pydantic import ValidationError
from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import opaque_token, token_hash
from app.db.base import utcnow
from app.modules.auth.models import PasswordToken
from app.modules.users.models import RoleCode, User
from app.modules.users.schemas import ProfileInput

COLUMNS = [
    "Employee Number",
    "Full Name",
    "Work Email",
    "Location",
    "Department",
    "Job Title",
    "Reporting To",
    "Date Joined",
]
FIELDS = [
    "employee_id",
    "full_name",
    "email",
    "location",
    "department",
    "designation",
    "reporting_to",
    "date_joined",
]
MAX_ROWS = 200
MAX_BYTES = 5 * 1024 * 1024


def template():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Users"
    sheet.append(COLUMNS)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = "A1:H201"
    for col in range(1, len(COLUMNS) + 1):
        sheet.column_dimensions[chr(64 + col)].width = 30 if col in [2, 3, 7] else 22
        cell = sheet.cell(1, col)
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = PatternFill("solid", fgColor="702C91")
        cell.alignment = Alignment(wrap_text=True)
        for row in range(2, 202):
            sheet.cell(row, col).number_format = "dd-mmm-yyyy" if col == 8 else "@"
    sheet.row_dimensions[1].height = 30
    notes = workbook.create_sheet("Instructions")
    for line in [
        "MyCareer - HRMS user import",
        "Fill Users with up to 200 new accounts. Do not change the header row.",
        "Employee Number is stored as Employee ID. Format it as text to retain leading zeros.",
        "Reporting To may contain a manager's Employee Number or unique Full Name. Leave blank when there is no manager.",
        "A person referenced in Reporting To is assigned the Manager role; all other imported accounts are Employees.",
        "HR / Super Admin accounts are created separately in MyCareer, not imported from this sheet.",
        "Location is stored separately from Country. Date Joined may be an Excel date or YYYY-MM-DD; leave blank if unknown.",
        "Duplicates, ambiguous manager names and reporting cycles are rejected. Existing accounts are never updated.",
        "No passwords belong in this workbook. Confirmed imports generate private one-use setup links.",
        "Setup links use the configured expiry (7 days by default); hand them off privately.",
        "Upload to preview, fix reported rows, then confirm the complete batch.",
    ]:
        notes.append([line])
    notes.column_dimensions["A"].width = 110
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def read_file(data):
    if not data or len(data) > MAX_BYTES:
        raise AppError(422, "INVALID_IMPORT", "Upload an .xlsx file no larger than 5 MB.")
    try:
        with ZipFile(BytesIO(data)) as package:
            files = package.infolist()
            if (
                len(files) > 2000
                or sum(f.file_size for f in files) > 32 * 1024 * 1024
                or any(
                    "externallinks/" in f.filename.casefold() or f.filename.casefold().endswith(".bin")
                    for f in files
                )
            ):
                raise ValueError("Unsupported workbook content")
        book = load_workbook(BytesIO(data), read_only=True, data_only=False, keep_links=False)
        try:
            if "Users" not in book.sheetnames:
                raise ValueError("Missing Users sheet")
            sheet = book["Users"]
            if sheet.max_row > MAX_ROWS + 1 or sheet.max_column > len(COLUMNS):
                raise ValueError("Too many rows or columns")
            header = [
                cell.value for cell in next(sheet.iter_rows(min_row=1, max_row=1, max_col=len(COLUMNS)))
            ]
            if header != COLUMNS:
                raise ValueError("Unexpected column headers")
            rows = []
            for number, cells in enumerate(sheet.iter_rows(min_row=2, max_col=len(COLUMNS)), start=2):
                if all(cell.value in [None, ""] for cell in cells):
                    continue
                if any(cell.data_type == "f" for cell in cells):
                    raise ValueError("Formulas are not allowed")
                values = {key: cell.value for key, cell in zip(FIELDS, cells, strict=True)}
                rows.append({"row": number, **values})
            if not rows:
                raise ValueError("The Users sheet has no accounts")
            return rows
        finally:
            book.close()
    except (
        BadZipFile,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        DefusedXmlException,
        ParseError,
        InvalidFileException,
        RuntimeError,
    ):
        raise AppError(
            422,
            "INVALID_IMPORT",
            "Use the supplied HRMS .xlsx template, with 1-200 rows, exact headers and no formulas, macros or external links.",
        ) from None


def text(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        raise ValueError("Expected text")
    if isinstance(value, int):
        return str(value)
    if not isinstance(value, str):
        raise ValueError("Expected text")
    return value.strip()


def joined_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            raise ValueError("Date Joined must be an Excel date or YYYY-MM-DD") from None
    raise ValueError("Date Joined must be an Excel date or YYYY-MM-DD")


def validate_rows(db, rows):
    normalized = []
    errors = []
    seen_ids = set()
    seen_emails = set()
    existing = db.scalars(select(User)).all()
    by_id = {u.employee_id.casefold(): u for u in existing}
    existing_by_name = defaultdict(list)
    for user in existing:
        if user.active:
            existing_by_name[user.full_name.casefold()].append(user)
    emails = {u.email.casefold() for u in existing}
    for row in rows:
        number = row["row"]
        try:
            profile = ProfileInput(
                employee_id=text(row.get("employee_id")),
                full_name=text(row.get("full_name")),
                email=text(row.get("email")),
                department=text(row.get("department")),
                designation=text(row.get("designation")),
                country="",
                location=text(row.get("location")),
                date_joined=joined_date(row.get("date_joined")),
            )
            manager_reference = text(row.get("reporting_to") or row.get("manager_employee_id"))
            identifier = profile.employee_id.casefold()
            email = profile.email.casefold()
            if identifier in seen_ids or identifier in by_id:
                raise ValueError("Employee ID already exists or is repeated in this file")
            if email in seen_emails or email in emails:
                raise ValueError("Email already exists or is repeated in this file")
            seen_ids.add(identifier)
            seen_emails.add(email)
            profile_data = profile.model_dump()
            profile_data["date_joined"] = profile.date_joined.isoformat() if profile.date_joined else None
            normalized.append(
                {
                    "row": number,
                    **profile_data,
                    "reporting_to": manager_reference,
                }
            )
        except ValidationError as exc:
            errors.append(
                {
                    "row": number,
                    "message": "Check profile fields: " + ", ".join(str(e["loc"][0]) for e in exc.errors()),
                }
            )
        except ValueError as exc:
            errors.append({"row": number, "message": str(exc)})
    incoming = {r["employee_id"].casefold(): r for r in normalized}
    incoming_by_name = defaultdict(list)
    for row in normalized:
        incoming_by_name[row["full_name"].casefold()].append(row)

    def resolve_manager(reference):
        key = reference.casefold()
        if key in incoming:
            return "incoming", incoming[key]
        if key in by_id:
            return "existing", by_id[key]
        matches = [("incoming", item) for item in incoming_by_name.get(key, [])]
        matches.extend(("existing", item) for item in existing_by_name.get(key, []))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError("Reporting To matches more than one person; use the manager's Employee Number")
        raise ValueError("Reporting To must match an Employee Number or unique active Manager name")

    resolved = {}
    inferred_manager_ids = set()
    for row in normalized:
        reference = row["reporting_to"]
        if not reference:
            continue
        try:
            resolved[row["row"]] = resolve_manager(reference)
        except ValueError as exc:
            errors.append({"row": row["row"], "message": str(exc)})
            continue
        kind, target = resolved[row["row"]]
        if kind == "incoming":
            inferred_manager_ids.add(target["employee_id"].casefold())

    for row in normalized:
        row["role"] = "MANAGER" if row["employee_id"].casefold() in inferred_manager_ids else "EMPLOYEE"

    for row in normalized:
        row["manager_employee_id"] = ""
        if not row["reporting_to"] or row["row"] not in resolved:
            continue
        kind, target = resolved[row["row"]]
        if kind == "incoming":
            row["manager_employee_id"] = target["employee_id"]
            if target["role"] != "MANAGER":
                errors.append(
                    {"row": row["row"], "message": "Reporting To must identify a Manager in this file"}
                )
        else:
            row["manager_employee_id"] = target.employee_id
            if not target.active or RoleCode.MANAGER not in target.roles:
                errors.append(
                    {"row": row["row"], "message": "Reporting To must identify an active existing Manager"}
                )

    def manager_employee_id(employee_id):
        key = employee_id.casefold()
        imported = incoming.get(key)
        if imported:
            return imported["manager_employee_id"].casefold()
        old_user = by_id.get(key)
        parent = db.get(User, old_user.manager_id) if old_user and old_user.manager_id else None
        return parent.employee_id.casefold() if parent else ""

    for row in normalized:
        manager = row["manager_employee_id"].casefold()
        visited = {row["employee_id"].casefold()}
        while manager:
            if manager in visited:
                errors.append(
                    {"row": row["row"], "message": "Self-manager or circular reporting relationship"}
                )
                break
            visited.add(manager)
            manager = manager_employee_id(manager)
    return normalized, errors


def setup_token(db, user, settings):
    raw = opaque_token()
    expires = utcnow() + timedelta(minutes=settings.setup_link_minutes)
    db.add(PasswordToken(user_id=user.id, token_hash=token_hash(raw), expires_at=expires))
    base_url = (settings.public_base_url or settings.allowed_origins[0]).rstrip("/")
    setup_path = "/#reset=" + raw
    return {
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "setup_url": base_url + setup_path,
        "alternate_setup_url": settings.alternate_public_base_url.rstrip("/") + setup_path
        if settings.alternate_public_base_url
        else None,
        "expires_at": expires,
    }


def setup_email_instructions(link, settings):
    setup_url = link["setup_url"]
    alternate = link["alternate_setup_url"]
    setup = f"Set your password using this one-time link: {setup_url}"
    if alternate:
        setup = (
            "Choose either address to set your MyCareer password.\n"
            f"Main setup link: {setup_url}\n"
            f"Alternate setup link: {alternate}"
        )
    base_url = (settings.public_base_url or settings.allowed_origins[0]).rstrip("/")
    instructions = (
        f"{setup}\n\nYour setup access expires at {link['expires_at']:%d %b %Y, %H:%M} UTC "
        "and can only be used once.\n\n"
        f"After setup, sign in at {base_url} with your work email ({link['email']}) and the password you chose."
    )
    if alternate:
        instructions += f"\nAlternate sign-in address: {settings.alternate_public_base_url.rstrip('/')}"
    return instructions
