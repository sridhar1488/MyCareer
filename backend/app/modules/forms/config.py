from app.core.errors import AppError
from app.modules.forms.schemas import FormConfig
from app.modules.forms.text_limits import HEADER_LIMIT, RESPONSE_LIMIT, TEXT_MINIMUM, is_single_character


def stored_config(config):
    return FormConfig.model_validate(
        {
            **config,
            "goal_title_max_length": max(
                TEXT_MINIMUM, min(config.get("goal_title_max_length", HEADER_LIMIT), HEADER_LIMIT)
            ),
            "goal_description_max_length": max(
                TEXT_MINIMUM, min(config.get("goal_description_max_length", RESPONSE_LIMIT), RESPONSE_LIMIT)
            ),
        }
    )


def config_for(definition):
    if definition.get("form_config"):
        return stored_config(definition["form_config"])
    return FormConfig(
        name="Workbook annual appraisal",
        competencies=[
            {"id": f"competency-{i}", "label": label, "leadership": i == 10}
            for i, label in enumerate(definition["competencies"])
        ],
    )


def text_errors(config, answers, owner, required=False, *, enforce_minimum=False):
    questions = {q.id: q for s in config.text_sections if s.owner == owner for q in s.questions}
    errors = []
    for key, value in answers.items():
        if key not in questions or not isinstance(value, str) or len(value) > 10000:
            errors.append("Only configured text questions for this form and respondent may be answered.")
        elif enforce_minimum and is_single_character(value):
            errors.append(f"{questions[key].label}: enter at least {TEXT_MINIMUM} characters or NA.")
    if required:
        for key, question in questions.items():
            if question.required and not answers.get(key, "").strip():
                errors.append(f"Complete: {question.label}")
    return errors


def validate_employee(config, data, required=False):
    if len(data.goals) > config.goals_limit or len(data.contributions) > (
        config.contributions_limit if config.contributions_enabled else 0
    ):
        raise AppError(
            422, "FORM_LIMIT", "The response exceeds the goal or contribution limits in this form."
        )
    errors = text_errors(
        config, data.development.extra_answers, "EMPLOYEE", required, enforce_minimum=required
    )
    if not config.development_enabled and any(
        value for key, value in data.development.model_dump().items() if key != "extra_answers"
    ):
        errors.append("The standard development section is disabled in this form.")
    if errors:
        raise AppError(422, "INVALID_FORM_RESPONSES", " ".join(errors))
