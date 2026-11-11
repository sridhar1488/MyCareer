from datetime import UTC, date, datetime

from pydantic import AwareDatetime, BaseModel, Field, StrictInt, field_validator, model_validator

from app.modules.auth.schemas import StrictInput

CYCLE_PARTICIPANT_LIMIT = 10_000


class CycleInput(StrictInput):
    title: str = Field(min_length=1, max_length=150)
    period_start: date
    period_end: date
    submission_deadline: AwareDatetime
    min_goals: StrictInt = Field(ge=1, le=5)
    allow_late_submission: bool
    participant_ids: list[str] = Field(min_length=1, max_length=CYCLE_PARTICIPANT_LIMIT)
    form_version_id: str = Field(default="workbook-ye2025-v1", max_length=36)

    @field_validator("title")
    @classmethod
    def trim_title(cls, value):
        if not value.strip():
            raise ValueError("Enter a cycle title")
        return value.strip()

    @field_validator("submission_deadline")
    @classmethod
    def utc_deadline(cls, value):
        return value.astimezone(UTC).replace(tzinfo=None)

    @model_validator(mode="after")
    def valid_period(self):
        if self.period_end < self.period_start or len(set(self.participant_ids)) != len(self.participant_ids):
            raise ValueError("Invalid appraisal period or duplicate participants")
        return self


# These models also load saved responses and snapshots. Draft saves enforce the
# current limits while allowing existing text to round-trip.
class ItemInput(StrictInput):
    description: str = Field(max_length=5000)
    employee_narrative: str = Field(max_length=10000)


class DevelopmentInput(StrictInput):
    business_achievements: str = Field(default="", max_length=10000)
    development_achievements: str = Field(default="", max_length=10000)
    six_month_growth: str = Field(default="", max_length=10000)
    development_needs: str = Field(default="", max_length=10000)
    development_plan: str = Field(default="", max_length=10000)
    support_requested: str = Field(default="", max_length=10000)
    extra_answers: dict[str, str] = Field(default_factory=dict, max_length=100)

    @field_validator("extra_answers", mode="before")
    @classmethod
    def existing_answers(cls, value):
        return value or {}


class SelfAssessmentInput(StrictInput):
    expected_version: int = Field(ge=1)
    goals: list[ItemInput] = Field(max_length=100)
    contributions: list[ItemInput] = Field(max_length=100)
    development: DevelopmentInput


class TransitionInput(StrictInput):
    expected_version: int = Field(ge=1)


class CycleResponse(BaseModel):
    id: str
    title: str
    period_start: date
    period_end: date
    submission_deadline: datetime
    min_goals: int
    allow_late_submission: bool
    state: str
    version: int
    participant_ids: list[str]
    scoring_policy_version: str
    form_version_id: str


class CyclePage(BaseModel):
    items: list[CycleResponse]
    total: int
    page: int
    page_size: int


class ParticipantOption(BaseModel):
    id: str
    full_name: str
    employee_id: str
    department: str
    manager_id: str | None
    role: str


class ParticipantPage(BaseModel):
    items: list[ParticipantOption]
    total: int
    page: int
    page_size: int


class BulkParticipantOptions(BaseModel):
    participant_ids: list[str]
    skipped: int


class AppraisalSummary(BaseModel):
    id: str
    cycle_id: str
    cycle_title: str
    period_start: date
    period_end: date
    state: str
    version: int
    manager_name: str
    submission_deadline: datetime
    started_at: datetime | None
    submitted_at: datetime | None


class AppraisalPage(BaseModel):
    items: list[AppraisalSummary]
    total: int
    page: int
    page_size: int


class AppraisalResponse(AppraisalSummary):
    last_draft_saved_at: AwareDatetime | None = None
    identity_snapshot: dict
    content_revision: int
    form_definition: dict
    min_goals: int
    allow_late_submission: bool
    goals: list[ItemInput]
    contributions: list[ItemInput]
    development: DevelopmentInput
    editable: bool
    return_reason: str | None = None


class HistoryRow(BaseModel):
    id: str
    actor_name: str
    from_state: str | None
    to_state: str
    reason: str | None
    occurred_at: datetime


class HistoryPage(BaseModel):
    items: list[HistoryRow]
    total: int
    page: int
    page_size: int


class RevisionResponse(BaseModel):
    revision: int
    submitted_at: datetime
    responses: "EmployeeResponses"


class EmployeeResponses(BaseModel):
    goals: list[ItemInput]
    contributions: list[ItemInput]
    development: DevelopmentInput


class CycleEdit(CycleInput):
    expected_version: int = Field(ge=1)
