from datetime import datetime

from pydantic import BaseModel, Field, StrictBool, StrictInt

from app.modules.appraisals.schemas import AppraisalResponse, EmployeeResponses
from app.modules.auth.schemas import StrictInput
from app.modules.forms.text_limits import TEXT_MINIMUM, ResponseText


# Review and calibration saves validate edits against the current limit.
# Historical evaluations still use these models when read back.
class RatingInput(StrictInput):
    rating: StrictInt | None = Field(default=None, ge=1, le=5)
    comment: str = Field(default="", max_length=10000)
    not_applicable: StrictBool = False
    applicability_reason: str = Field(default="", max_length=2000)


class EvaluationInput(StrictInput):
    goals: list[RatingInput] = Field(max_length=100)
    contributions: list[RatingInput] = Field(max_length=100)
    competencies: list[RatingInput] = Field(max_length=50)
    strengths: str = Field(default="", max_length=10000)
    improvements: str = Field(default="", max_length=10000)
    extra_answers: dict[str, str] = Field(default_factory=dict, max_length=100)


class ReviewCommand(StrictInput):
    expected_version: StrictInt = Field(ge=1)
    submitted_revision: StrictInt = Field(ge=1)


class SaveReview(ReviewCommand):
    evaluation: EvaluationInput


class ReturnReview(ReviewCommand):
    reason: ResponseText = Field(min_length=TEXT_MINIMUM)


class ReleaseReview(ReviewCommand):
    review_meeting_confirmed: StrictBool


class CalibrationSave(StrictInput):
    expected_version: StrictInt = Field(ge=1)
    submitted_revision: StrictInt = Field(ge=1)
    evaluation: EvaluationInput
    reason: ResponseText = ""


class CalibrationApprove(StrictInput):
    expected_version: StrictInt = Field(ge=1)
    submitted_revision: StrictInt = Field(ge=1)
    reason: ResponseText = ""


class AcknowledgeInput(StrictInput):
    expected_version: StrictInt = Field(ge=1)


class ExactValue(BaseModel):
    numerator: int
    denominator: int
    display: str


class SectionScore(BaseModel):
    key: str
    title: str
    weight_percent: int
    rated_count: int
    average: ExactValue
    weighted: ExactValue
    empty_as_zero: bool
    enabled: bool = True


class ScoreResult(BaseModel):
    policy_version: str
    sections: list[SectionScore]
    overall: ExactValue
    calculated_overall: ExactValue | None = Field(default=None, exclude_if=lambda value: value is None)


class TeamRow(BaseModel):
    id: str
    employee_name: str
    employee_id: str
    department: str
    cycle_title: str
    state: str
    version: int
    submitted_revision: int
    submitted_at: datetime | None
    submission_deadline: datetime


class TeamPage(BaseModel):
    items: list[TeamRow]
    total: int
    page: int
    page_size: int


class ReviewEventRow(BaseModel):
    id: str
    appraisal_version: int
    submitted_revision: int
    action: str
    evaluation: EvaluationInput
    occurred_at: datetime


class ReviewEventPage(BaseModel):
    items: list[ReviewEventRow]
    total: int
    page: int
    page_size: int


class ReleasedResult(BaseModel):
    appraisal_version: int
    submitted_revision: int
    identity_snapshot: dict
    form_definition: dict
    employee_responses: EmployeeResponses
    evaluation: EvaluationInput
    score: ScoreResult
    policy: dict
    finalized_at: datetime
    released_at: datetime | None
    acknowledged_at: datetime | None


class ReviewResponse(BaseModel):
    appraisal: AppraisalResponse
    submitted_revision: int
    employee_responses: EmployeeResponses
    evaluation: EvaluationInput
    draft_is_current: bool
    final_result: ReleasedResult | None
    score_preview: ScoreResult | None
    validation_errors: list[str]
    policy: dict
