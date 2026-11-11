from collections import Counter
from io import BytesIO

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.chart import BarChart, Reference, ScatterChart, Series
from openpyxl.chart.axis import ChartLines
from openpyxl.chart.data_source import AxDataSource, NumData, NumVal, StrData, StrRef, StrVal
from openpyxl.chart.series import SeriesLabel
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.drawing.text import CharacterProperties
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from app.modules.hr.schemas import AnalyticsResponse, ScoreDistribution

PURPLE = "6D2888"


def _write_row(sheet, row, values, start=1):
    for column, value in enumerate(values, start):
        cell = sheet.cell(row, column)
        if isinstance(value, str):
            cell.value = ILLEGAL_CHARACTERS_RE.sub("", value)
            cell.data_type = "s"
        else:
            cell.value = value


def _headers(sheet, row, labels, start=1):
    _write_row(sheet, row, labels, start)
    for column in range(start, start + len(labels)):
        cell = sheet.cell(row, column)
        cell.fill = PatternFill("solid", fgColor="482563")
        cell.font = Font(color="FFFFFF", bold=True)


def _table(sheet, labels, rows, widths, formats=None):
    _headers(sheet, 1, labels)
    for row, values in enumerate(rows, 2):
        _write_row(sheet, row, values)
        for column, number_format in (formats or {}).items():
            sheet.cell(row, column).number_format = number_format
    for column, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(column)].width = width
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions


def _style_chart(chart, title, subtitle):
    chart.title = f"{title}\n{subtitle}"
    chart.title.overlay = False
    heading, detail = chart.title.tx.rich.p
    heading.r[0].rPr = CharacterProperties(sz=1500, b=True, solidFill="250644")
    detail.r[0].rPr = CharacterProperties(sz=1000, solidFill="665C6C")
    chart.x_axis.delete = chart.y_axis.delete = False
    chart.x_axis.tickLblPos = "low"
    chart.y_axis.tickLblPos = "nextTo"
    chart.x_axis.majorGridlines = None
    grid = GraphicalProperties()
    grid.line.solidFill = "E1D8E8"
    chart.y_axis.majorGridlines = ChartLines(spPr=grid)


def _number_cache(sheet, reference):
    points = []
    for index, row in enumerate(range(reference.min_row, reference.max_row + 1)):
        value = sheet.cell(row, reference.min_col).value
        if value is not None:
            points.append(NumVal(idx=index, v=value))
    return NumData(ptCount=reference.max_row - reference.min_row + 1, pt=points)


def _score_bars(sheet, title, category_column, score_column, anchor, *, vertical=False):
    if sheet.max_row < 2:
        return
    chart = BarChart()
    _style_chart(chart, title, "Average approved score / 5")
    if vertical:
        chart.type = "col"
        chart.x_axis.axPos = "b"
        chart.y_axis.axPos = "l"
    else:
        chart.type = "bar"
        chart.x_axis.axPos = "l"
        chart.x_axis.scaling.orientation = "maxMin"
        chart.y_axis.axPos = "b"
        chart.y_axis.crosses = "max"
    chart.y_axis.scaling.min = 0
    chart.y_axis.scaling.max = 5
    chart.y_axis.majorUnit = 1
    chart.y_axis.number_format = "0"
    chart.legend = None
    chart.width = min(44, max(23, sheet.max_row * 2)) if vertical else 23
    chart.height = 13 if vertical else min(30, max(8, sheet.max_row * 0.7))
    scores = Reference(sheet, min_col=score_column, min_row=2, max_row=sheet.max_row)
    chart.add_data(scores)
    categories = Reference(sheet, min_col=category_column, min_row=2, max_row=sheet.max_row)
    names = [
        StrVal(idx=index, v=sheet.cell(row, category_column).value)
        for index, row in enumerate(range(2, sheet.max_row + 1))
    ]
    series = chart.series[0]
    series.title = SeriesLabel(v="Average approved score")
    series.cat = AxDataSource(
        strRef=StrRef(f=str(categories), strCache=StrData(ptCount=len(names), pt=names))
    )
    series.val.numRef.numCache = _number_cache(sheet, scores)
    series.graphicalProperties.solidFill = PURPLE
    series.graphicalProperties.line.noFill = True
    sheet.add_chart(chart, anchor)


def _distribution_chart(sheet, distribution: ScoreDistribution, scores: list[float]):
    first_data_row = 31
    _headers(sheet, first_data_row - 1, ("Bin start", "Bin end", "Observed count"))
    _headers(sheet, first_data_row - 1, ("Reference score", "Fitted count"), 5)
    _headers(sheet, first_data_row - 1, ("Outline score", "Outline count"), 8)
    _headers(sheet, first_data_row - 1, ("Employee score", "Plot position"), 11)
    for col in ("A", "B", "C", "E", "F", "H", "I", "K", "L"):
        sheet.column_dimensions[col].width = 19

    for index, count in enumerate(distribution.bin_counts):
        start = 1 + index * 0.5
        end = start + 0.5
        _write_row(sheet, first_data_row + index, (start, end, count))
        outline = ((start, 0), (start, count), (end, count), (end, 0))
        for offset, pair in enumerate(outline):
            _write_row(sheet, first_data_row + index * 4 + offset, pair, 8)
    for index, count in enumerate(distribution.reference_counts):
        _write_row(sheet, first_data_row + index, (round(1 + index * 0.05, 2), count), 5)

    lanes: Counter[float] = Counter()
    dot_band = distribution.maximum / 4
    dot_step = dot_band / (max(Counter(scores).values()) + 1)
    for index, score in enumerate(scores):
        lanes[score] += 1
        _write_row(sheet, first_data_row + index, (score, -dot_step * lanes[score]), 11)

    chart = ScatterChart()
    _style_chart(chart, "Employee score distribution", "Final score / 5 · Count of scores")
    chart.scatterStyle = "lineMarker"
    chart.x_axis.scaling.min = 1
    chart.x_axis.scaling.max = 5
    chart.x_axis.majorUnit = 1
    chart.x_axis.axPos = "b"
    chart.x_axis.crosses = "min"
    chart.y_axis.axPos = "l"
    chart.y_axis.scaling.min = -dot_band
    chart.y_axis.scaling.max = distribution.maximum
    chart.y_axis.majorUnit = distribution.maximum / 4
    chart.y_axis.number_format = '0;"";0'
    chart.y_axis.crossesAt = 1
    chart.legend.position = "b"
    chart.legend.overlay = False
    chart.width = 25
    chart.height = 12

    for title, x_column, length, color in (
        ("Observed score counts", 8, 4 * len(distribution.bin_counts), "B98ACB"),
        ("Bell curve reference", 5, len(distribution.reference_counts), PURPLE),
        ("Individual employee score", 11, len(scores), "CF2379"),
    ):
        last_row = first_data_row + length - 1
        x = Reference(sheet, min_col=x_column, min_row=first_data_row, max_row=last_row)
        y = Reference(sheet, min_col=x_column + 1, min_row=first_data_row, max_row=last_row)
        series = Series(y, x, title=title)
        series.xVal.numRef.numCache = _number_cache(sheet, x)
        series.yVal.numRef.numCache = _number_cache(sheet, y)
        if x_column == 11:
            series.graphicalProperties.line.noFill = True
            series.marker.symbol = "circle"
            series.marker.size = 5
            series.marker.graphicalProperties.solidFill = color
            series.marker.graphicalProperties.line.solidFill = color
        else:
            series.marker.symbol = "none"
            series.graphicalProperties.line.solidFill = color
            series.smooth = False
        chart.series.append(series)
    sheet.add_chart(chart, "A5")


def analytics_workbook(data: AnalyticsResponse, cycle_title: str) -> bytes:
    book = Workbook()
    summary = book.active
    summary.title = "Summary"
    overview = data.summary
    _table(
        summary,
        ("Metric", "Value"),
        (
            ("Appraisal cycle", cycle_title),
            ("Appraisals in scope", overview.appraisal_count),
            ("HR approved", overview.approved_count),
            ("Approval rate", float(overview.approval_percent) / 100),
            (
                "Average approved score / 5",
                float(overview.approved_average) if overview.approved_average is not None else None,
            ),
        ),
        (32, 55),
    )
    summary["B5"].number_format = "0.0%"
    summary["B6"].number_format = "0.0"

    distribution_sheet = book.create_sheet("Score distribution")
    _headers(distribution_sheet, 1, ("Final scores from 1 to 5",))
    distribution_sheet.merge_cells("A1:D1")
    scores = [float(point.score) for point in data.score_points]
    plotted = [score for score in scores if 1 <= score <= 5]
    if data.distribution:
        _write_row(
            distribution_sheet, 2, ("Mean score / 5", data.distribution.mean, "Scores plotted", len(plotted))
        )
        distribution_sheet["B2"].number_format = "0.0"
        _write_row(
            distribution_sheet, 3, ("The bell curve is fitted to these results and is a reference only.",)
        )
        _distribution_chart(distribution_sheet, data.distribution, plotted)
    else:
        _write_row(distribution_sheet, 2, ("No HR-approved scores are available in the 1–5 chart range.",))

    employees = book.create_sheet("Employee scores")
    _table(
        employees,
        ("Employee ID", "Employee", "Final score / 5", "Shown on chart"),
        (
            (point.employee_id, point.employee_name, score, "Yes" if 1 <= score <= 5 else "No")
            for point, score in zip(data.score_points, scores, strict=True)
        ),
        (20, 36, 20, 20),
        {3: "0.0"},
    )

    departments = book.create_sheet("Departments")
    _table(
        departments,
        ("Department", "Appraisals", "HR approved", "Approval rate", "Average score / 5"),
        (
            (
                item.department,
                item.appraisal_count,
                item.approved_count,
                float(item.approval_percent) / 100,
                float(item.average_score) if item.average_score is not None else None,
            )
            for item in data.departments
        ),
        (30, 15, 15, 16, 22),
        {4: "0.0%", 5: "0.0"},
    )
    _score_bars(departments, "Department score comparison", 1, 5, "G2", vertical=True)

    performers = book.create_sheet("Top performers")
    _table(
        performers,
        (
            "Rank",
            "Employee ID",
            "Employee",
            "Department",
            "Manager",
            "Approved appraisals",
            "Average score / 5",
        ),
        (
            (
                rank,
                person.employee_id,
                person.employee_name,
                person.department,
                person.manager_name,
                person.approved_appraisals,
                float(person.average_score),
            )
            for rank, person in enumerate(data.top_performers, 1)
        ),
        (9, 18, 30, 24, 30, 22, 22),
        {7: "0.0"},
    )
    _score_bars(performers, "Top 5 performers", 3, 7, "I2")

    output = BytesIO()
    book.save(output)
    return output.getvalue()
