"""Branded, paginated report layout for preserved final evaluations."""

from datetime import UTC, datetime
from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    CondPageBreak,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.modules.forms.config import config_for

ASSETS = Path(__file__).with_name("assets")
pdfmetrics.registerFont(TTFont("LeapMetrics", str(ASSETS / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("LeapMetrics-Bold", str(ASSETS / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFontFamily(
    "LeapMetrics",
    normal="LeapMetrics",
    bold="LeapMetrics-Bold",
    italic="LeapMetrics",
    boldItalic="LeapMetrics-Bold",
)

PURPLE = colors.HexColor("#482563")
DARK = colors.HexColor("#250644")
PINK = colors.HexColor("#FE2072")
PALE = colors.HexColor("#F5F0F8")
INK = colors.HexColor("#363436")
MUTED = colors.HexColor("#665C6C")
LINE = colors.HexColor("#E1D8E8")
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 38
WIDTH = PAGE_WIDTH - 2 * MARGIN

DEVELOPMENT_LABELS = {
    "business_achievements": "Most important business and project achievements",
    "development_achievements": "Personal and professional development achievements",
    "six_month_growth": "Growth and development priorities for the next six months",
    "development_needs": "Technical and personal development needs",
    "development_plan": "Development plan for the forthcoming year",
    "support_requested": "Support requested",
}


def render_pdf(records):
    stream = BytesIO()
    generated = datetime.now(UTC).strftime("%d %b %Y, %H:%M UTC")
    body = ParagraphStyle(
        "Report body",
        fontName="LeapMetrics",
        fontSize=8.7,
        leading=13,
        textColor=INK,
        spaceAfter=0,
        splitLongWords=True,
    )
    styles = {
        "body": body,
        "title": ParagraphStyle(
            "Title",
            parent=body,
            fontName="LeapMetrics-Bold",
            fontSize=23,
            leading=29,
            textColor=DARK,
            spaceAfter=8,
        ),
        "cycle": ParagraphStyle(
            "Cycle", parent=body, fontSize=12, leading=17, textColor=MUTED, spaceAfter=16
        ),
        "kicker": ParagraphStyle(
            "Kicker",
            parent=body,
            fontName="LeapMetrics-Bold",
            fontSize=8,
            leading=12,
            textColor=PURPLE,
            spaceAfter=8,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=body,
            fontName="LeapMetrics-Bold",
            fontSize=10,
            leading=15,
            textColor=colors.white,
        ),
        "label": ParagraphStyle(
            "Label", parent=body, fontName="LeapMetrics-Bold", fontSize=8, leading=12, textColor=PURPLE
        ),
        "column": ParagraphStyle(
            "Column", parent=body, fontName="LeapMetrics-Bold", fontSize=8, leading=12, textColor=colors.white
        ),
        "small": ParagraphStyle("Small", parent=body, fontSize=7.2, leading=10.5, textColor=MUTED),
        "score_label": ParagraphStyle(
            "Score label",
            parent=body,
            fontName="LeapMetrics-Bold",
            fontSize=8,
            leading=12,
            textColor=colors.white,
        ),
        "score": ParagraphStyle(
            "Score", parent=body, fontName="LeapMetrics-Bold", fontSize=30, leading=39, textColor=colors.white
        ),
        "rating": ParagraphStyle(
            "Rating",
            parent=body,
            fontName="LeapMetrics-Bold",
            fontSize=11,
            leading=16,
            textColor=PURPLE,
            alignment=TA_CENTER,
        ),
    }

    def p(value, style="body"):
        text = str(value) if value is not None and value != "" else "Not provided"
        text = "".join(c for c in text if ord(c) >= 32 or c in "\n\t")
        return Paragraph(escape(text).replace("\n", "<br/>"), styles[style])

    def date(value):
        return value.strftime("%d %b %Y, %H:%M UTC") if value else "Pending"

    def table(rows, widths=None, header=True, commands=()):
        widths = widths or [WIDTH]

        def chunks(cell, width):
            """Bound row height so long narratives split at safe row boundaries."""
            if cell == "":
                return [[Spacer(0, 0)]]
            pending = list(cell) if isinstance(cell, list) else [cell]
            result, current, height = [], [], 0
            while pending:
                item = pending.pop(0)
                _, item_height = item.wrap(width - 20, 100000)
                remaining = 190 - height
                if item_height <= remaining:
                    current.append(item)
                    height += item_height
                    continue
                pieces = item.split(width - 20, remaining) if isinstance(item, Paragraph) else []
                if pieces:
                    current.append(pieces[0])
                    pending = pieces[1:] + pending
                else:
                    pending.insert(0, item)
                if not current:
                    raise ValueError("Report text could not be split into a printable row")
                result.append(current)
                current, height = [], 0
            if current:
                result.append(current)
            return result or [[Spacer(0, 0)]]

        printable_rows = []
        for row in rows:
            cells = [chunks(cell, width) for cell, width in zip(row, widths, strict=True)]
            for part in range(max(len(cell) for cell in cells)):
                printable_rows.append([cell[part] if part < len(cell) else "" for cell in cells])
        value = Table(
            printable_rows,
            colWidths=widths,
            repeatRows=1 if header else 0,
            splitByRow=1,
            splitInRow=0,
            hAlign="LEFT",
        )
        rules = [
            ("FONTNAME", (0, 0), (-1, -1), "LeapMetrics"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.45, LINE),
        ]
        if header:
            rules.extend(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
                ]
            )
        value.setStyle(TableStyle(rules + list(commands)))
        return value

    story = []

    def section(number, title):
        story.append(CondPageBreak(160))
        story.append(Spacer(1, 16))
        band = table(
            [[p(f"{number:02d}   {title}", "section")]], commands=[("BACKGROUND", (0, 0), (-1, -1), PURPLE)]
        )
        band.keepWithNext = True
        band.spaceAfter = 8
        story.append(band)

    def response(label, answer):
        story.append(
            table([[p(label, "label")], [p(answer)]], commands=[("BACKGROUND", (0, 0), (-1, 0), PALE)])
        )
        story.append(Spacer(1, 9))

    for position, (appraisal, cycle, result) in enumerate(records):
        if position:
            story.append(PageBreak())
        identity = result.identity_snapshot
        cfg = config_for(result.form_definition)
        story.extend(
            [
                p("PERFORMANCE & DEVELOPMENT", "kicker"),
                p("Final evaluation report", "title"),
                p(cycle.title, "cycle"),
            ]
        )
        metadata = [
            [
                p("EMPLOYEE", "label"),
                p(identity.get("employee_name")),
                p("EMPLOYEE ID", "label"),
                p(identity.get("employee_id")),
            ],
            [
                p("DEPARTMENT", "label"),
                p(identity.get("department")),
                p("DESIGNATION", "label"),
                p(identity.get("designation")),
            ],
            [
                p("MANAGER", "label"),
                p(identity.get("manager_name")),
                p("COUNTRY", "label"),
                p(identity.get("country")),
            ],
        ]
        story.append(
            table(
                metadata,
                [92, 172, 92, WIDTH - 356],
                header=False,
                commands=[("BACKGROUND", (0, 0), (0, -1), PALE), ("BACKGROUND", (2, 0), (2, -1), PALE)],
            )
        )
        story.append(Spacer(1, 14))
        score_card = table(
            [
                [
                    [
                        p("OVERALL PERFORMANCE SCORE", "score_label"),
                        p(f"{result.score.overall.display} / 5", "score"),
                    ],
                    [
                        p("HR APPROVED", "label"),
                        p(date(result.finalized_at)),
                        Spacer(1, 7),
                        p(
                            "Employee receipt acknowledged"
                            if result.acknowledged_at
                            else "Released to employee"
                            if result.released_at
                            else "Awaiting release to employee",
                            "body",
                        ),
                    ],
                ]
            ],
            [WIDTH * 0.48, WIDTH * 0.52],
            header=False,
            commands=[
                ("BACKGROUND", (0, 0), (0, 0), PURPLE),
                ("BACKGROUND", (1, 0), (1, 0), PALE),
                ("LEFTPADDING", (0, 0), (-1, -1), 16),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ],
        )
        story.extend([score_card, Spacer(1, 14)])
        scores = [
            [
                p(label, "column")
                for label in ["Performance section", "Weight", "Rated items", "Average / 5", "Weighted score"]
            ]
        ]
        for score in result.score.sections:
            scores.append(
                [
                    p(score.title),
                    p(f"{score.weight_percent}%"),
                    p(score.rated_count),
                    p(score.average.display if score.enabled else "Excluded"),
                    p(score.weighted.display),
                ]
            )
        scores.append(
            [p("Overall score", "label"), p("100%"), "", "", p(result.score.overall.display, "label")]
        )
        story.append(
            table(scores, [215, 53, 65, 87, WIDTH - 420], commands=[("BACKGROUND", (0, -1), (-1, -1), PALE)])
        )
        story.extend(
            [
                Spacer(1, 6),
                p(
                    "Scores are preserved from manager approval. Exact values are used before display rounding; weighted components may not sum exactly at displayed precision.",
                    "small",
                ),
            ]
        )

        count = 0
        for key in cfg.section_order:
            if key in ["contributions", "competencies", "development"] and not getattr(cfg, f"{key}_enabled"):
                continue
            custom = next((s for s in cfg.text_sections if s.id == key), None)
            count += 1
            section(count, custom.title if custom else getattr(cfg, f"{key}_title"))
            if key in ["goals", "contributions"]:
                items = getattr(result.employee_responses, key)
                for index, item in enumerate(items):
                    rating = getattr(result.evaluation, key)[index]
                    if index:
                        story.append(CondPageBreak(100))
                    title = f"{index + 1:02d}   {item.description}"
                    descriptor = table(
                        [[p(title, "label")]], header=False, commands=[("BACKGROUND", (0, 0), (-1, -1), PALE)]
                    )
                    descriptor.keepWithNext = descriptor.wrap(WIDTH, 100000)[1] < 160
                    story.append(descriptor)
                    rows = [
                        [
                            p(f"EMPLOYEE SELF-ASSESSMENT / ITEM {index + 1:02d}", "label"),
                            p("MANAGER EVALUATION", "label"),
                        ],
                        [
                            p(item.employee_narrative),
                            [p(f"Rating: {rating.rating} / 5", "label"), Spacer(1, 6), p(rating.comment)],
                        ],
                    ]
                    value = table(
                        rows,
                        [WIDTH * 0.62, WIDTH * 0.38],
                        commands=[
                            ("BACKGROUND", (0, 0), (-1, 0), PALE),
                            ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                        ],
                    )
                    story.extend([value, Spacer(1, 10)])
                if not items:
                    story.append(
                        table(
                            [
                                [
                                    p(
                                        "No contributions submitted. This section scores zero with its configured weight retained."
                                    )
                                ]
                            ],
                            header=False,
                            commands=[("BACKGROUND", (0, 0), (-1, -1), PALE)],
                        )
                    )
            elif key == "competencies":
                rows = [
                    [
                        p(label, "column")
                        for label in ["Competency", "Rating", "Manager assessment / N/A reason"]
                    ]
                ]
                for label, rating in zip(
                    result.form_definition["competencies"], result.evaluation.competencies, strict=True
                ):
                    notes = [p(rating.comment)] if rating.comment else []
                    if rating.not_applicable:
                        notes.extend([p("Not applicable", "label"), p(rating.applicability_reason)])
                    rows.append(
                        [
                            p(label),
                            p("N/A" if rating.not_applicable else rating.rating, "rating"),
                            notes or p("Not provided"),
                        ]
                    )
                story.append(table(rows, [WIDTH * 0.39, WIDTH * 0.13, WIDTH * 0.48]))
            elif key == "development":
                for field, label in DEVELOPMENT_LABELS.items():
                    response(label, getattr(result.employee_responses.development, field))
            elif custom:
                answers = (
                    result.employee_responses.development.extra_answers
                    if custom.owner == "EMPLOYEE"
                    else result.evaluation.extra_answers
                )
                story.extend([p(f"Completed by: {custom.owner.title()}", "small"), Spacer(1, 6)])
                for question in custom.questions:
                    response(question.label, answers.get(question.id))
        section(count + 1, "Manager evaluation")
        response("Strengths - what the employee did particularly well", result.evaluation.strengths)
        response(
            "Development priorities - how the employee could be more effective",
            result.evaluation.improvements,
        )
        section(count + 2, "Approval and employee receipt")
        approval = [
            [
                p(label, "column")
                for label in ["Manager approval", "Released to employee", "Employee acknowledgement"]
            ],
            [
                [p(identity.get("manager_name"), "label"), p(date(result.finalized_at))],
                p(date(result.released_at)),
                p(date(result.acknowledged_at)),
            ],
        ]
        story.append(table(approval, [WIDTH / 3] * 3))
        story.extend(
            [
                Spacer(1, 10),
                p(
                    "Manager approval preserves this evaluation. Employee acknowledgement records receipt and does not alter the score.",
                    "small",
                ),
                Spacer(1, 8),
                p(
                    f"Form: {result.form_definition.get('form_name', cfg.name)} | Policy: {result.score.policy_version}",
                    "small",
                ),
                p(
                    f"Appraisal reference: {appraisal.id} | Submitted revision: {result.submitted_revision}",
                    "small",
                ),
            ]
        )
    if not records:
        story.extend(
            [p("Final evaluation report", "title"), p("No finalized evaluations match these filters.")]
        )

    def page_frame(canvas, document):
        canvas.saveState()
        canvas.setFillColor(DARK)
        canvas.rect(0, PAGE_HEIGHT - 60, PAGE_WIDTH, 60, fill=1, stroke=0)
        canvas.setFillColor(PINK)
        canvas.rect(0, PAGE_HEIGHT - 63, PAGE_WIDTH, 3, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("LeapMetrics-Bold", 15)
        canvas.drawString(MARGIN, PAGE_HEIGHT - 28, "MyCareer")
        canvas.setFont("LeapMetrics", 8)
        canvas.drawString(MARGIN, PAGE_HEIGHT - 43, "MedImpact International")
        canvas.setFont("LeapMetrics-Bold", 8)
        canvas.drawRightString(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 33, "CONFIDENTIAL  |  FINAL EVALUATION")
        canvas.setStrokeColor(LINE)
        canvas.line(MARGIN, 38, PAGE_WIDTH - MARGIN, 38)
        canvas.setFillColor(MUTED)
        canvas.setFont("LeapMetrics", 7)
        canvas.drawString(MARGIN, 25, "Confidential - Human Resources")
        canvas.drawCentredString(PAGE_WIDTH / 2, 25, f"Generated {generated}")
        canvas.drawRightString(PAGE_WIDTH - MARGIN, 25, f"Page {document.page}")
        canvas.restoreState()

    class ReportDocument(SimpleDocTemplate):
        def afterPage(self):
            page_frame(self.canv, self)

    ReportDocument(
        stream,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=85,
        bottomMargin=54,
        title="MyCareer - Final Evaluation Report",
        author="MedImpact International",
        allowSplitting=1,
    ).build(story)
    return stream.getvalue()
