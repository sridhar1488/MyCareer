from datetime import timedelta
from io import BytesIO
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from defusedxml.common import DefusedXmlException
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.worksheet.datavalidation import DataValidation
from pydantic import ValidationError
from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import opaque_token, token_hash
from app.db.base import utcnow
from app.modules.auth.models import PasswordToken
from app.modules.users.models import RoleCode, User
from app.modules.users.schemas import ProfileInput

COLUMNS = [
    "employee_id",
    "full_name",
    "email",
    "department",
    "designation",
    "country",
    "role",
    "super_admin",
    "manager_employee_id",
]
MAX_ROWS = 200
MAX_BYTES = 5 * 1024 * 1024


def template():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Users"
    sheet.append(COLUMNS)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = "A1:I201"
    for col in range(1, 10):
        sheet.column_dimensions[chr(64 + col)].width = 30 if col in [2, 3] else 24
        cell = sheet.cell(1, col)
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = PatternFill("solid", fgColor="702C91")
        cell.alignment = Alignment(wrap_text=True)
        for row in range(2, 202):
            sheet.cell(row, col).number_format = "@"
    sheet.row_dimensions[1].height = 30
    for column, values in [("G", "EMPLOYEE,MANAGER,SUPER_ADMIN"), ("H", "TRUE,FALSE")]:
        validation = DataValidation(type="list", formula1=f'"{values}"', allow_blank=True)
        sheet.add_data_validation(validation)
        validation.add(f"{column}2:{column}201")
    notes = workbook.create_sheet("Instructions")
    for line in [
        "MyCareer - new user import",
        "Fill Users with up to 200 new accounts. Do not change the header row.",
        "employee_id and manager_employee_id are text: retain leading zeros.",
        "Role: EMPLOYEE, MANAGER, or SUPER_ADMIN. Blank means EMPLOYEE.",
        "super_admin: TRUE adds HR / Super Admin access to a MANAGER account. Employee accounts cannot have this access.",
        "Use SUPER_ADMIN for an HR account that does not also need the Manager role.",
        "manager_employee_id may identify an existing active Manager or another Manager in this file.",
        "Leave manager_employee_id blank for top-level managers or accounts awaiting assignment.",
        "Duplicates and reporting cycles are rejected. Existing accounts are never updated.",
        "No passwords belong in this workbook. Confirmed imports generate private one-use setup links.",
        "Setup links use the configured reset expiry (30 minutes by default); hand them off privately.",
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
                values = {key: cell.value for key, cell in zip(COLUMNS, cells, strict=True)}
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
            "Use the supplied .xlsx template, with 1-200 rows, exact headers and no formulas, macros or external links.",
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


def validate_rows(db, rows):
    normalized = []
    errors = []
    seen_ids = set()
    seen_emails = set()
    existing = db.scalars(select(User)).all()
    by_id = {u.employee_id.casefold(): u for u in existing}
    emails = {u.email.casefold() for u in existing}
    for row in rows:
        number = row["row"]
        try:
            profile = ProfileInput(
                **{
                    k: text(row.get(k))
                    for k in ["employee_id", "full_name", "email", "department", "designation", "country"]
                }
            )
            role = text(row.get("role")) or "EMPLOYEE"
            if role not in ["EMPLOYEE", "MANAGER", "SUPER_ADMIN"]:
                raise ValueError("Role must be EMPLOYEE, MANAGER, or SUPER_ADMIN")
            flag = row.get("super_admin")
            if isinstance(flag, str):
                flag = flag.strip().upper()
            if not (
                flag is None or type(flag) is bool or isinstance(flag, str) and flag in ["", "TRUE", "FALSE"]
            ):
                raise ValueError("super_admin must be TRUE or FALSE")
            admin = flag is True or flag == "TRUE"
            if role == "EMPLOYEE" and admin:
                raise ValueError("Employee accounts cannot be assigned Super Admin access")
            admin = admin or role == "SUPER_ADMIN"
            manager = text(row.get("manager_employee_id"))
            identifier = profile.employee_id.casefold()
            email = profile.email.casefold()
            if identifier in seen_ids or identifier in by_id:
                raise ValueError("Employee ID already exists or is repeated in this file")
            if email in seen_emails or email in emails:
                raise ValueError("Email already exists or is repeated in this file")
            seen_ids.add(identifier)
            seen_emails.add(email)
            normalized.append(
                {
                    "row": number,
                    **profile.model_dump(),
                    "role": role,
                    "super_admin": admin,
                    "manager_employee_id": manager,
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
    for row in normalized:
        manager = row["manager_employee_id"].casefold()
        if not manager:
            continue
        candidate = incoming.get(manager)
        old = by_id.get(manager)
        if not (
            candidate
            and candidate["role"] == "MANAGER"
            or old
            and old.active
            and RoleCode.MANAGER in old.roles
        ):
            errors.append(
                {
                    "row": row["row"],
                    "message": "Manager ID must identify an active existing Manager or a Manager in this file",
                }
            )
            continue
        visited = {row["employee_id"].casefold()}
        while manager:
            if manager in visited:
                errors.append(
                    {"row": row["row"], "message": "Self-manager or circular reporting relationship"}
                )
                break
            visited.add(manager)
            if manager in incoming:
                manager = incoming[manager]["manager_employee_id"].casefold()
            else:
                old = by_id.get(manager)
                next_user = db.get(User, old.manager_id) if old and old.manager_id else None
                manager = next_user.employee_id.casefold() if next_user else ""
    return normalized, errors


def setup_token(db, user, settings):
    raw = opaque_token()
    expires = utcnow() + timedelta(minutes=settings.setup_link_minutes)
    db.add(PasswordToken(user_id=user.id, token_hash=token_hash(raw), expires_at=expires))
    base_url = (settings.public_base_url or settings.allowed_origins[0]).rstrip("/")
    return {
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "setup_url": base_url + "/#reset=" + raw,
        "expires_at": expires,
    }
