from collections import Counter
from html import escape
from io import BytesIO

from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    CondPageBreak,
    Flowable,
    KeepTogether,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.modules.hr.pdf_report import DARK, INK, LINE, MUTED, PALE, PINK, PURPLE
from app.modules.hr.schemas import AnalyticsResponse, DepartmentAnalytics, ScoreDistribution

MARGIN = 42
WIDTH = 511
HISTOGRAM = colors.HexColor("#D6B5E0")
BODY = ParagraphStyle("Analytics body", fontName="LeapMetrics", fontSize=9, leading=13, textColor=INK)
MUTED_BODY = ParagraphStyle("Analytics note", parent=BODY, fontSize=8, textColor=MUTED)
HEADING = ParagraphStyle(
    "Analytics heading",
    parent=BODY,
    fontName="LeapMetrics-Bold",
    fontSize=13,
    leading=18,
    textColor=DARK,
    spaceBefore=15,
    spaceAfter=7,
    keepWithNext=True,
)
COLUMN_HEADER = ParagraphStyle(
    "Analytics column",
    parent=BODY,
    fontName="LeapMetrics-Bold",
    fontSize=8,
    textColor=colors.white,
)


def _text(value, style=BODY):
    return Paragraph(escape(str(value)), style)


def _table(headers, rows, widths):
    table = LongTable(
        [[_text(header, COLUMN_HEADER) for header in headers]]
        + [[value if isinstance(value, Flowable) else _text(value) for value in row] for row in rows],
        colWidths=widths,
        repeatRows=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, -1), (-1, -1), 0.5, LINE),
            ]
        )
    )
    return table


def _score_bar(score: str | None) -> Drawing:
    bar = Drawing(114, 14)
    bar.add(Rect(0, 4, 74, 6, rx=3, ry=3, fillColor=LINE, strokeColor=None))
    if score is not None and float(score) > 0:
        bar.add(Rect(0, 4, 74 * float(score) / 5, 6, rx=3, ry=3, fillColor=PURPLE, strokeColor=None))
    bar.add(
        String(
            83, 3, score if score is not None else "-", fontName="LeapMetrics-Bold", fontSize=9, fillColor=INK
        )
    )
    return bar


def _department_chart(
    departments: list[DepartmentAnalytics], heading: Paragraph | None = None
) -> KeepTogether:
    chart = Drawing(WIDTH, 147)
    left, right = 30, 7
    bottom, top = 3, 118
    spacing = (WIDTH - left - right) / len(departments)
    bar_width = min(46, spacing * 0.55)

    def y(value):
        return bottom + (top - bottom) * value / 5

    chart.add(
        String(left, 136, "Average approved score / 5", fontName="LeapMetrics", fontSize=8, fillColor=MUTED)
    )
    for score in range(6):
        chart.add(Line(left, y(score), WIDTH - right, y(score), strokeColor=LINE, strokeWidth=0.65))
        chart.add(
            String(
                left - 7,
                y(score) - 2,
                str(score),
                fontName="LeapMetrics",
                fontSize=8,
                fillColor=MUTED,
                textAnchor="end",
            )
        )
    for index, department in enumerate(departments):
        if department.average_score is None:
            continue
        score = float(department.average_score)
        center = left + (index + 0.5) * spacing
        if score > 0:
            chart.add(
                Rect(
                    center - bar_width / 2,
                    bottom,
                    bar_width,
                    y(score) - bottom,
                    fillColor=PURPLE,
                    strokeColor=None,
                )
            )
        chart.add(
            String(
                center,
                y(score) + 4,
                department.average_score,
                fontName="LeapMetrics-Bold",
                fontSize=8,
                fillColor=PURPLE,
                textAnchor="middle",
            )
        )
    label_style = ParagraphStyle("Department chart label", parent=MUTED_BODY, alignment=TA_CENTER, leading=11)
    labels = Table(
        [["", *[_text(item.department, label_style) for item in departments], ""]],
        colWidths=[left, *[spacing] * len(departments), right],
        hAlign="LEFT",
    )
    labels.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    content = [chart, labels, Spacer(1, 9)]
    if heading is not None:
        content.insert(0, heading)
    return KeepTogether(content)


def _bell_curve(distribution: ScoreDistribution, scores: list[float]) -> Drawing:
    chart = Drawing(WIDTH, 216)
    left, right = 33, WIDTH - 15
    baseline, top = 66, 187

    def x(score):
        return left + (score - 1) / 4 * (right - left)

    def y(count):
        return baseline + (top - baseline) * count / distribution.maximum

    def label(at_x, at_y, text, anchor="start"):
        chart.add(
            String(at_x, at_y, text, fontName="LeapMetrics", fontSize=8, fillColor=MUTED, textAnchor=anchor)
        )

    label(left, 198, "Count of scores")
    for index in range(5):
        count = distribution.maximum * index // 4
        chart.add(Line(left, y(count), right, y(count), strokeColor=LINE, strokeWidth=0.65))
        label(left - 7, y(count) - 3, str(count), "end")
    for index, count in enumerate(distribution.bin_counts):
        if count:
            start = 1 + index / 2
            chart.add(
                Rect(
                    x(start) + 1,
                    baseline,
                    x(start + 0.5) - x(start) - 2,
                    y(count) - baseline,
                    fillColor=HISTOGRAM,
                    strokeColor=None,
                )
            )
    chart.add(
        PolyLine(
            [(x(1 + index * 0.05), y(count)) for index, count in enumerate(distribution.reference_counts)],
            strokeColor=PURPLE,
            strokeWidth=2,
        )
    )
    lanes: Counter[float] = Counter()
    dot_step = min(7, 18 / max(Counter(scores).values()))
    for score in scores:
        chart.add(
            Circle(
                x(score),
                baseline - 5 - lanes[score] * dot_step,
                min(2.7, dot_step / 2),
                fillColor=PINK,
                strokeColor=None,
            )
        )
        lanes[score] += 1
    for score in range(1, 6):
        label(x(score), 34, str(score), "middle")
    label((left + right) / 2, 21, "Final score / 5", "middle")
    chart.add(Rect(33, 4, 9, 6, fillColor=HISTOGRAM, strokeColor=None))
    label(47, 3, "Observed counts")
    chart.add(Line(137, 7, 149, 7, strokeColor=PURPLE, strokeWidth=2))
    label(154, 3, "Bell curve reference")
    chart.add(Circle(253, 7, 2.5, fillColor=PINK, strokeColor=None))
    label(260, 3, "Individual scores")
    return chart


def analytics_pdf(data: AnalyticsResponse, cycle_title: str) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        title="MyCareer | HR analytics",
        author="MedImpact International",
        leftMargin=MARGIN - 6,
        rightMargin=MARGIN - 6,
        topMargin=60,
        bottomMargin=44,
    )

    def page_frame(canvas, doc):
        canvas.saveState()
        page_width, page_height = doc.pagesize
        canvas.setFillColor(DARK)
        canvas.rect(0, page_height - 43, page_width, 43, fill=1, stroke=0)
        canvas.setFont("LeapMetrics-Bold", 11)
        canvas.setFillColor(colors.white)
        canvas.drawString(MARGIN, page_height - 27, "MyCareer")
        canvas.setFont("LeapMetrics", 8)
        canvas.drawRightString(page_width - MARGIN, page_height - 27, "MedImpact International")
        canvas.setStrokeColor(LINE)
        canvas.line(MARGIN, 35, page_width - MARGIN, 35)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, 22, "Confidential | HR analytics")
        canvas.drawRightString(page_width - MARGIN, 22, f"Page {doc.page}")
        canvas.restoreState()

    summary = data.summary
    score = f"{summary.approved_average} / 5" if summary.approved_average is not None else "Pending"
    metrics = Table(
        [
            [
                _text(label, MUTED_BODY)
                for label in ("Appraisals in scope", "HR approved", "Average approved score")
            ],
            [
                _text(
                    value,
                    ParagraphStyle(
                        "Analytics metric", parent=HEADING, fontSize=17, spaceBefore=0, spaceAfter=0
                    ),
                )
                for value in (
                    summary.appraisal_count,
                    f"{summary.approved_count}  ({summary.approval_percent}%)",
                    score,
                )
            ],
        ],
        colWidths=[WIDTH / 3] * 3,
        hAlign="LEFT",
    )
    metrics.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("LINEBEFORE", (1, 0), (-1, -1), 1, colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 11),
                ("TOPPADDING", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 9),
            ]
        )
    )
    title = ParagraphStyle("Analytics title", parent=HEADING, fontSize=24, leading=29, spaceBefore=0)
    story = [
        _text("People and performance analytics", title),
        _text(cycle_title, MUTED_BODY),
        Spacer(1, 12),
        metrics,
    ]

    story.append(_text("Employee score distribution", HEADING))
    if data.distribution:
        plotted = [float(point.score) for point in data.score_points if 1 <= float(point.score) <= 5]
        story.extend(
            [
                _bell_curve(data.distribution, plotted),
                Spacer(1, 6),
                _text(
                    f"{len(plotted)} scores plotted. Mean {data.distribution.mean:.1f} / 5. The fitted curve is a reference only.",
                    MUTED_BODY,
                ),
            ]
        )
    else:
        story.append(_text("No HR-approved scores are available in the 1 to 5 chart range.", MUTED_BODY))

    story.append(_text("Top 5 performers", HEADING))
    if data.top_performers:
        story.append(
            _table(
                ("Rank", "Employee", "Department", "Manager", "Approved", "Average / 5"),
                (
                    (
                        rank,
                        f"{person.employee_name} ({person.employee_id})",
                        person.department,
                        person.manager_name,
                        person.approved_appraisals,
                        _score_bar(person.average_score),
                    )
                    for rank, person in enumerate(data.top_performers, 1)
                ),
                (45, 111, 78, 80, 63, 134),
            )
        )
    else:
        story.append(_text("No HR-approved evaluations are available for this selection.", MUTED_BODY))

    department_heading = _text("Department score comparison", HEADING)
    if data.departments:
        count = len(data.departments)
        panels = (count + 5) // 6
        per_panel = (count + panels - 1) // panels
        for start in range(0, count, per_panel):
            story.append(
                _department_chart(
                    data.departments[start : start + per_panel],
                    department_heading if start == 0 else None,
                )
            )
        story.append(
            _table(
                ("Department", "Appraisals", "HR approved", "Approval rate", "Average / 5"),
                (
                    (
                        item.department,
                        item.appraisal_count,
                        item.approved_count,
                        f"{item.approval_percent}%",
                        item.average_score if item.average_score is not None else "-",
                    )
                    for item in data.departments
                ),
                (152, 68, 73, 84, 134),
            )
        )
    else:
        story.append(department_heading)
        story.append(_text("No appraisals are available for this selection.", MUTED_BODY))

    detail_heading = ParagraphStyle("Analytics detail heading", parent=HEADING, keepWithNext=False)
    story.extend([CondPageBreak(85), _text("Individual employee scores", detail_heading)])
    if data.score_points:
        story.append(
            _table(
                ("Employee ID", "Employee", "Final score / 5", "Shown on chart"),
                (
                    (
                        point.employee_id,
                        point.employee_name,
                        point.score,
                        "Yes" if 1 <= float(point.score) <= 5 else "No",
                    )
                    for point in sorted(
                        data.score_points,
                        key=lambda point: (point.employee_name.casefold(), point.employee_id),
                    )
                ),
                (100, 201, 100, 110),
            )
        )
    else:
        story.append(_text("No individual scores are available for this selection.", MUTED_BODY))

    document.build(story, onFirstPage=page_frame, onLaterPages=page_frame)
    return output.getvalue()
