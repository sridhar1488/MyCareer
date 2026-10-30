"""Authoritative, versioned scoring. Exact fractions are persisted, never floats."""

from fractions import Fraction

from app.core.errors import AppError
from app.modules.forms.config import config_for, text_errors
from app.modules.reviews.schemas import EvaluationInput, ExactValue, ScoreResult, SectionScore

POLICY_VERSION = "mi-2026-10-20-v1"


def policy(version, definition=None):
    if version != POLICY_VERSION:
        raise AppError(409, "UNKNOWN_SCORING_POLICY", "This cycle's scoring policy is unavailable.")
    rules = {
        "version": POLICY_VERSION,
        "approved_on": "2026-10-20",
        "weights": {"goals": 70, "contributions": 10, "competencies": 20},
        "denominator": "populated applicable items",
        "empty_contributions": "zero; retain 10 percent weight",
        "missing_ratings": "reject finalization, never substitute zero",
        "not_applicable": "leadership competency only, with reason; exclude from denominator",
        "supporting_comments_required": True,
        "precision": "exact rational arithmetic; no intermediate rounding",
        "display_rounding": "half-up",
        "average_and_overall_decimal_places": 1,
        "weighted_component_decimal_places": 2,
        "overall_category": None,
        "review_meeting_required": True,
        "review_meeting_timing": "after HR approval and before manager release to employee",
        "release": "separate assigned-manager action",
        "acknowledgement": "employee receipt event; score unchanged",
    }
    if definition:
        config = config_for(definition)
        rules.update(
            weights=config.weights.model_dump(),
            form_version_id=definition.get("form_version_id", "workbook-ye2025-v1"),
            form_name=config.name,
            empty_contributions=f"zero; retain {config.weights.contributions} percent weight",
            leadership_competencies=[c.id for c in config.competencies if c.leadership],
        )
    return rules


def exact(value: Fraction, places: int):
    # Integer rounding avoids Decimal context precision and recurring-fraction ties.
    scale = 10**places
    quotient, remainder = divmod(value.numerator * scale, value.denominator)
    rounded = quotient + (2 * remainder >= value.denominator)
    display = f"{rounded // scale}.{rounded % scale:0{places}d}"
    return ExactValue(numerator=value.numerator, denominator=value.denominator, display=display)


def validation_errors(evaluation: EvaluationInput, content, competency_count=11, definition=None):
    errors = []
    config = config_for(definition) if definition else None
    allowed_na = {i for i, c in enumerate(config.competencies) if c.leadership} if config else {10}
    if not content["goals"]:
        errors.append("At least one submitted goal is required.")
    expected = {
        "goals": len(content["goals"]),
        "contributions": len(content["contributions"]),
        "competencies": competency_count,
    }
    for section, count in expected.items():
        entries = getattr(evaluation, section)
        if len(entries) != count:
            errors.append(f"{section.title()}: review exactly {count} submitted items.")
        for index, entry in enumerate(entries):
            label = f"{section.title()} {index + 1}"
            if entry.not_applicable:
                if section != "competencies" or index not in allowed_na:
                    errors.append(f"{label}: only leadership can be marked N/A.")
                if entry.rating is not None:
                    errors.append(f"{label}: N/A cannot also have a rating.")
                if not entry.applicability_reason.strip():
                    errors.append(f"{label}: explain why leadership is not applicable.")
            else:
                if entry.rating is None:
                    errors.append(f"{label}: enter a whole-number rating from 1 to 5.")
                if not entry.comment.strip():
                    errors.append(f"{label}: enter a supporting manager comment.")
    if not evaluation.strengths.strip():
        errors.append("Complete the manager strengths narrative.")
    if not evaluation.improvements.strip():
        errors.append("Complete the manager improvement narrative.")
    if config:
        errors.extend(text_errors(config, evaluation.extra_answers, "MANAGER", True))
    return errors


def calculate(
    evaluation: EvaluationInput, content, version=POLICY_VERSION, competency_count=11, definition=None
):
    rules = policy(version, definition)
    config = config_for(definition) if definition else None
    errors = validation_errors(evaluation, content, competency_count, definition)
    if errors:
        raise AppError(422, "INCOMPLETE_REVIEW", " ".join(errors))
    sections = []
    total = Fraction(0)
    for key, title in [
        ("goals", "Goals / job responsibilities"),
        ("contributions", "Organizational contributions"),
        ("competencies", "Professional competencies"),
    ]:
        entries = [entry.rating for entry in getattr(evaluation, key) if not entry.not_applicable]
        enabled = True if not config or key == "goals" else getattr(config, f"{key}_enabled")
        if not entries and key != "contributions" and enabled:
            raise AppError(422, "INCOMPLETE_REVIEW", f"{title} requires applicable ratings.")
        average = Fraction(sum(entries), len(entries)) if entries else Fraction(0)
        weight = rules["weights"][key]
        weighted = average * Fraction(weight, 100)
        total += weighted
        sections.append(
            SectionScore(
                key=key,
                title=getattr(config, f"{key}_title") if config else title,
                weight_percent=weight,
                rated_count=len(entries),
                average=exact(average, 1),
                weighted=exact(weighted, 2),
                empty_as_zero=not entries,
                enabled=enabled,
            )
        )
    return ScoreResult(policy_version=version, sections=sections, overall=exact(total, 1))
