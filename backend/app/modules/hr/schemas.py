from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from app.modules.forms.text_limits import TEXT_MINIMUM, ResponseText
from app.modules.reviews.schemas import ReviewCommand


class OverallScoreOverride(ReviewCommand):
    score: Annotated[Decimal, Field(ge=0, le=5, decimal_places=1)] | None
    reason: ResponseText = Field(min_length=TEXT_MINIMUM)


class CalibrationQueueRow(BaseModel):
    id: str
    employee_name: str
    employee_id: str
    department: str
    manager_name: str
    cycle_title: str
    form_name: str
    state: str
    version: int
    submitted_revision: int
    manager_submitted_at: datetime
    manager_overall: str
    calibrated_overall: str
    calculated_overall: str | None
    strengths: str
    improvements: str


class CalibrationQueuePage(BaseModel):
    items: list[CalibrationQueueRow]
    total: int
    page: int
    page_size: int


class MonitorRow(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    employee_active: bool
    department: str
    designation: str
    manager_id: str
    manager_name: str
    manager_active: bool
    cycle_id: str
    cycle_title: str
    cycle_state: str
    status: str
    pending_action: str
    responsible_name: str | None
    submission_deadline: datetime
    overdue: bool
    deadline_enforced: bool
    submitted_at: datetime | None
    finalized_at: datetime | None
    released_at: datetime | None
    acknowledged_at: datetime | None


class ManagerStatus(BaseModel):
    manager_id: str
    manager_name: str
    manager_active: bool
    total: int
    status_counts: dict[str, int]


class MonitorResponse(BaseModel):
    total: int
    status_counts: dict[str, int]
    items: list[MonitorRow]
    managers: list[ManagerStatus]
    manager_total: int
    page: int
    page_size: int
    view: str


class FilterOption(BaseModel):
    id: str
    label: str


class MonitorOptions(BaseModel):
    cycles: list[FilterOption]
    managers: list[FilterOption]


class AnalyticsSummary(BaseModel):
    appraisal_count: int
    approved_count: int
    approval_percent: str
    approved_average: str | None


class DepartmentAnalytics(BaseModel):
    department: str
    appraisal_count: int
    approved_count: int
    approval_percent: str
    average_score: str | None


class TopPerformer(BaseModel):
    employee_id: str
    employee_name: str
    department: str
    manager_name: str
    average_score: str
    approved_appraisals: int


class ScorePoint(BaseModel):
    employee_id: str
    employee_name: str
    score: str


class ScoreDistribution(BaseModel):
    bin_counts: list[int]
    reference_counts: list[float]
    mean: float
    maximum: int


class AnalyticsResponse(BaseModel):
    summary: AnalyticsSummary
    departments: list[DepartmentAnalytics]
    top_performers: list[TopPerformer]
    score_points: list[ScorePoint]
    distribution: ScoreDistribution | None
