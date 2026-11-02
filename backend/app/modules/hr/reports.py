"""Exports use the preserved sign-off, never editable drafts or recalculated scores."""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill

from app.modules.forms.config import config_for


def narratives(result):
    cfg = config_for(result.form_definition)
    for key in ("goals", "contributions"):
        for i, item in enumerate(getattr(result.employee_responses, key)):
            rating = getattr(result.evaluation, key)[i]
            yield (
                getattr(cfg, f"{key}_title"),
                f"{i + 1}. {item.description}",
                item.employee_narrative,
                rating,
            )
    for i, label in enumerate(result.form_definition["competencies"]):
        yield cfg.competencies_title, label, "", result.evaluation.competencies[i]
    for key, value in result.employee_responses.development.model_dump().items():
        if key != "extra_answers" and cfg.development_enabled:
            yield cfg.development_title, key.replace("_", " ").title(), value, None
    for section in cfg.text_sections:
        answers = (
            result.employee_responses.development.extra_answers
            if section.owner == "EMPLOYEE"
            else result.evaluation.extra_answers
        )
        for q in section.questions:
            yield section.title, f"{section.owner}: {q.label}", answers.get(q.id, ""), None
    yield "Manager evaluation", "Strengths", result.evaluation.strengths, None
    yield "Manager evaluation", "Improvements", result.evaluation.improvements, None


def excel(records):
    book = Workbook()
    summary = book.active
    summary.title = "Evaluations"
    summary.append(
        [
            "Cycle",
            "Employee ID",
            "Employee",
            "Department",
            "Manager",
            "Status",
            "Approved Date",
            "Released Date",
            "Acknowledged Date",
            "Overall / 5",
        ]
    )
    scores = book.create_sheet("Section scores")
    scores.append(
        [
            "Section",
            "Enabled",
            "Weight %",
            "Rated items",
            "Average / 5",
            "Weighted score",
        ]
    )
    responses = book.create_sheet("Responses")
    responses.append(
        [
            "Section",
            "Question / item",
            "Response",
            "Manager rating",
            "Manager comment",
            "N/A",
            "N/A reason",
        ]
    )
    for appraisal, cycle, result in records:
        identity = result.identity_snapshot
        summary.append(
            [
                cycle.title,
                identity.get("employee_id", ""),
                identity.get("employee_name", ""),
                identity.get("department", ""),
                identity.get("manager_name", ""),
                appraisal.state,
                result.finalized_at,
                result.released_at,
                result.acknowledged_at,
                float(result.score.overall.display),
            ]
        )
        for section in result.score.sections:
            scores.append(
                [
                    section.title,
                    section.enabled,
                    section.weight_percent,
                    section.rated_count,
                    float(section.average.display),
                    float(section.weighted.display),
                ]
            )
        for title, label, text, rating in narratives(result):
            responses.append(
                [
                    title,
                    label,
                    text,
                    rating.rating if rating else None,
                    rating.comment if rating else "",
                    rating.not_applicable if rating else False,
                    rating.applicability_reason if rating else "",
                ]
            )
    for sheet in book:
        sheet.freeze_panes = "B2"
        sheet.auto_filter.ref = sheet.dimensions
        for row in sheet:
            for cell in row:
                if isinstance(cell.value, str):
                    cell.value = ILLEGAL_CHARACTERS_RE.sub("", cell.value)
                    cell.data_type = "s"  # User text must never become an Excel formula.
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                if cell.row == 1:
                    cell.fill = PatternFill("solid", fgColor="482563")
                    cell.font = Font(color="FFFFFF", bold=True)
                elif hasattr(cell.value, "year"):
                    cell.number_format = "yyyy-mm-dd hh:mm"
                elif isinstance(cell.value, float):
                    cell.number_format = "0.00" if sheet == scores and cell.column == 6 else "0.0"
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = 25 if sheet != responses else 38
        sheet.row_dimensions[1].height = 38
    stream = BytesIO()
    book.save(stream)
    return stream.getvalue()


def pdf(records):
    from app.modules.hr.pdf_report import render_pdf

    return render_pdf(records)
