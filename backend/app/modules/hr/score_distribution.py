from math import ceil, exp, pi, sqrt

from app.modules.hr.schemas import ScoreDistribution, ScorePoint


def score_distribution(points: list[ScorePoint]) -> ScoreDistribution | None:
    scores = [float(point.score) for point in points]
    scores = [score for score in scores if 1 <= score <= 5]
    if not scores:
        return None

    counts = [0] * 8
    for score in scores:
        counts[min(7, int((score - 1) * 2))] += 1

    mean = sum(scores) / len(scores)
    variance = sum((score - mean) ** 2 for score in scores) / len(scores)
    deviation = max(sqrt(variance), 0.15)
    scale = len(scores) * 0.5 / (deviation * sqrt(2 * pi))
    reference = [scale * exp(-0.5 * ((1 + i * 0.05 - mean) / deviation) ** 2) for i in range(81)]
    return ScoreDistribution(
        bin_counts=counts,
        reference_counts=reference,
        mean=mean,
        maximum=max(4, ceil(max(max(counts), max(reference)) * 1.2 / 4) * 4),
    )
