from typing import Literal

from pydantic import Field, StrictBool, StrictInt, model_validator

from app.modules.auth.schemas import StrictInput
from app.modules.forms.text_limits import HEADER_LIMIT, RESPONSE_LIMIT, TEXT_MINIMUM


class Weights(StrictInput):
    goals: StrictInt = Field(ge=0, le=100)
    contributions: StrictInt = Field(ge=0, le=100)
    competencies: StrictInt = Field(ge=0, le=100)


class Competency(StrictInput):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    label: str = Field(min_length=1, max_length=150)
    leadership: StrictBool = False


class TextQuestion(StrictInput):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    label: str = Field(min_length=1, max_length=500)
    required: StrictBool = False


class TextSection(StrictInput):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,40}$")
    title: str = Field(min_length=1, max_length=150)
    owner: Literal["EMPLOYEE", "MANAGER"] = "EMPLOYEE"
    questions: list[TextQuestion] = Field(min_length=1, max_length=50)


class FormConfig(StrictInput):
    name: str = Field(min_length=1, max_length=150)
    goals_title: str = Field(default="Goals and job responsibilities", min_length=1, max_length=150)
    contributions_title: str = Field(default="Organizational contributions", min_length=1, max_length=150)
    competencies_title: str = Field(default="Professional competencies", min_length=1, max_length=150)
    development_title: str = Field(default="Achievements and development", min_length=1, max_length=150)
    goals_limit: StrictInt = Field(default=100, ge=1, le=100)
    goal_title_max_length: StrictInt = Field(default=HEADER_LIMIT, ge=TEXT_MINIMUM, le=HEADER_LIMIT)
    goal_description_max_length: StrictInt = Field(default=RESPONSE_LIMIT, ge=TEXT_MINIMUM, le=RESPONSE_LIMIT)
    contributions_limit: StrictInt = Field(default=3, ge=1, le=100)
    contributions_enabled: StrictBool = True
    competencies_enabled: StrictBool = True
    development_enabled: StrictBool = True
    weights: Weights = Field(default_factory=lambda: Weights(goals=70, contributions=10, competencies=20))
    competencies: list[Competency] = Field(min_length=1, max_length=50)
    text_sections: list[TextSection] = Field(default_factory=list, max_length=20)
    section_order: list[str] = Field(
        default_factory=lambda: ["goals", "contributions", "competencies", "development"]
    )

    @model_validator(mode="after")
    def consistent(self):
        if sum(self.weights.model_dump().values()) != 100:
            raise ValueError("Section weights must total 100")
        if (
            not self.contributions_enabled
            and self.weights.contributions
            or not self.competencies_enabled
            and self.weights.competencies
        ):
            raise ValueError("Disabled sections must have zero weight")
        sections = ["goals", "contributions", "competencies", "development"] + [
            s.id for s in self.text_sections
        ]
        if len(set(sections)) != len(sections) or sorted(self.section_order) != sorted(sections):
            raise ValueError("List each section once in the form order")
        question_ids = [q.id for s in self.text_sections for q in s.questions]
        if len(set(question_ids)) != len(question_ids) or len(question_ids) > 100:
            raise ValueError("Use unique question identifiers, at most 100 questions")
        if (
            len({c.id for c in self.competencies}) != len(self.competencies)
            or sum(c.leadership for c in self.competencies) > 1
        ):
            raise ValueError("Use unique competencies and at most one optional leadership competency")
        if any(
            not v.strip()
            for v in [
                self.name,
                self.goals_title,
                self.contributions_title,
                self.competencies_title,
                self.development_title,
            ]
            + [c.label for c in self.competencies]
            + [s.title for s in self.text_sections]
            + [q.label for s in self.text_sections for q in s.questions]
        ):
            raise ValueError("Labels cannot be blank")
        return self


class SaveForm(StrictInput):
    expected_version: StrictInt = Field(ge=1)
    config: FormConfig


class FormCommand(StrictInput):
    expected_version: StrictInt = Field(ge=1)
