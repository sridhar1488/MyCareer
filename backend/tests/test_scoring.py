from fractions import Fraction

import pytest

from app.core.errors import AppError
from app.modules.reviews.schemas import EvaluationInput
from app.modules.reviews.scoring import calculate, exact


def evaluation(goals=(4,), contributions=(), competencies=None):
    def rated(values):
        return [{"rating": n, "comment": "Supporting evidence"} for n in values]

    return EvaluationInput(
        goals=rated(goals),
        contributions=rated(contributions),
        competencies=rated(competencies if competencies is not None else [5] * 11),
        strengths="Delivered results",
        improvements="Develop mentoring skills",
    )


def content(goal_count=1, contribution_count=0):
    return {"goals": [{}] * goal_count, "contributions": [{}] * contribution_count}


@pytest.mark.parametrize("rating", [1, 5])
def test_uniform_ratings_keep_their_exact_overall(rating):
    score = calculate(evaluation((rating,), (rating,), [rating] * 11), content(1, 1))
    assert score.overall.numerator == rating and score.overall.denominator == 1
    assert score.overall.display == f"{rating}.0"


def test_independent_weight_fixture_and_unused_slots():
    score = calculate(evaluation((4, 4), (3,), [5] * 11), content(2, 1))
    assert (score.overall.numerator, score.overall.denominator, score.overall.display) == (41, 10, "4.1")
    assert [s.rated_count for s in score.sections] == [2, 1, 11]
    assert [s.weighted.display for s in score.sections] == ["2.80", "0.30", "1.00"]


def test_empty_contributions_are_explicit_zero_with_weight_retained():
    score = calculate(evaluation(), content())
    assert (score.overall.numerator, score.overall.denominator, score.overall.display) == (19, 5, "3.8")
    contribution = score.sections[1]
    assert contribution.empty_as_zero and contribution.weight_percent == 10
    assert contribution.average.numerator == 0 and contribution.weighted.display == "0.00"


def test_empty_contributions_do_not_clamp_overall_to_the_item_scale():
    score = calculate(evaluation((1,), (), [1] * 11), content())
    assert (score.overall.numerator, score.overall.denominator, score.overall.display) == (9, 10, "0.9")


def test_one_hundred_goals_use_the_populated_count():
    score = calculate(evaluation([4] * 100, (), [5] * 11), content(100))
    assert score.sections[0].rated_count == 100
    assert score.sections[0].average.display == "4.0" and score.overall.display == "3.8"


def test_missing_rating_is_not_an_empty_section_zero():
    value = evaluation(contributions=(3,))
    value.contributions[0].rating = None
    with pytest.raises(AppError) as caught:
        calculate(value, content(1, 1))
    assert caught.value.code == "INCOMPLETE_REVIEW"


def test_leadership_na_excludes_only_leadership():
    value = evaluation()
    value.competencies[10].rating = None
    value.competencies[10].not_applicable = True
    value.competencies[10].applicability_reason = "No leadership responsibilities in this role"
    score = calculate(value, content())
    assert score.sections[2].rated_count == 10
    assert score.sections[2].average.display == "5.0"


@pytest.mark.parametrize(
    "attack",
    [
        "goal_na",
        "contribution_na",
        "required_competency_na",
        "missing_reason",
        "na_and_rating",
        "missing_comment",
        "empty_goals",
        "empty_competencies",
        "missing_strengths",
        "missing_improvements",
    ],
)
def test_incomplete_or_invalid_applicability_rejects_final_score(attack):
    value = evaluation(contributions=(3,))
    source = content(1, 1)
    if attack in ["goal_na", "contribution_na", "required_competency_na", "missing_reason", "na_and_rating"]:
        entry = (
            value.goals[0]
            if attack == "goal_na"
            else value.contributions[0]
            if attack == "contribution_na"
            else value.competencies[0]
            if attack == "required_competency_na"
            else value.competencies[10]
        )
        entry.not_applicable = True
        entry.rating = 4 if attack == "na_and_rating" else None
        entry.applicability_reason = "" if attack == "missing_reason" else "Reason"
    elif attack == "missing_comment":
        value.goals[0].comment = "  "
    elif attack == "empty_goals":
        value.goals = []
        source["goals"] = []
    elif attack == "empty_competencies":
        value.competencies = []
    elif attack == "missing_strengths":
        value.strengths = ""
    else:
        value.improvements = ""
    with pytest.raises(AppError):
        calculate(value, source)


def test_recurring_averages_are_not_rounded_before_weighting():
    score = calculate(evaluation((1, 1, 2), (3,), [5] * 11), content(3, 1))
    assert (score.sections[0].average.numerator, score.sections[0].average.denominator) == (4, 3)
    assert (score.overall.numerator, score.overall.denominator, score.overall.display) == (67, 30, "2.2")


@pytest.mark.parametrize(
    "value,places,expected",
    [
        (Fraction(81, 20), 1, "4.1"),
        (Fraction(83, 20), 1, "4.2"),
        (Fraction(1, 8), 2, "0.13"),
        (Fraction(1, 3), 2, "0.33"),
        (Fraction(0), 1, "0.0"),
    ],
)
def test_half_up_display_ties_and_recurring_fractions(value, places, expected):
    assert exact(value, places).display == expected
