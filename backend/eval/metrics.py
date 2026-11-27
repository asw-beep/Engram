"""Ranking metrics over gold sections, and the evidence-cutoff calibration.

A ranked chunk is relevant to a gold entry when it comes from the same document and its
heading path starts with the gold entry's headings, so a chunk in a subsection counts.
"""

import math
from collections.abc import Collection
from dataclasses import dataclass

from eval.dataset import Gold


@dataclass(frozen=True)
class Ranked:
    path: str
    headings: tuple[str, ...]


def in_section(item: Ranked, gold: Gold) -> bool:
    return item.path == gold.path and item.headings[: len(gold.headings)] == gold.headings


def recall_at(k: int, ranked: list[Ranked], gold: tuple[Gold, ...]) -> float:
    """1.0 only if every gold section has a chunk in the top k."""
    _require_gold(gold)
    top = ranked[:k]
    return 1.0 if all(any(in_section(item, entry) for item in top) for entry in gold) else 0.0


def reciprocal_rank(ranked: list[Ranked], gold: tuple[Gold, ...], k: int = 10) -> float:
    """1 / rank of the first chunk in any gold section within the top k, else 0."""
    _require_gold(gold)
    for rank, item in enumerate(ranked[:k], start=1):
        if any(in_section(item, entry) for entry in gold):
            return 1.0 / rank
    return 0.0


def ndcg_at(
    k: int, ranked: list[Ranked], gold: tuple[Gold, ...], outside: Collection[str] | None = None
) -> float:
    """NDCG where each gold section and each gold document earns credit once.

    The first chunk from each gold section earns 2. The first chunk from each gold
    document outside its gold sections earns 1. Every other chunk earns 0. The ideal
    ranking is one 2 per gold section, then one 1 per gold document that has text
    outside its gold sections. `outside` names those documents, as the corpus says;
    without it, every document whose gold entries all have headings is assumed to (an
    entry with no headings covers the whole document). So a ranking holding only the
    gold sections scores below 1 when the rest of a gold document could have been found.
    """
    _require_gold(gold)
    credited_sections: set[int] = set()
    credited_documents: set[str] = set()
    paths = {entry.path for entry in gold}
    gains = []
    for item in ranked[:k]:
        sections = [i for i, entry in enumerate(gold) if in_section(item, entry)]
        fresh = [i for i in sections if i not in credited_sections]
        if fresh:
            credited_sections.add(fresh[0])
            gains.append(2)
        elif not sections and item.path in paths and item.path not in credited_documents:
            credited_documents.add(item.path)
            gains.append(1)
        else:
            gains.append(0)
    partial_documents = [
        p
        for p in sorted(paths)
        if all(e.headings for e in gold if e.path == p) and (outside is None or p in outside)
    ]
    ideal = ([2] * len(gold) + [1] * len(partial_documents))[:k]
    return _dcg(gains) / _dcg(ideal)


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile: the smallest value with at least p% of values at or below."""
    if not values:
        raise ValueError("percentile of no values")
    if not 0 <= p <= 100:
        raise ValueError(f"percentile {p} is outside 0 to 100")
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def balanced_accuracy(
    answerable_top: list[float], unanswerable_top: list[float], cutoff: float
) -> float:
    """Mean of the share of answerable questions that pass and unanswerable ones refused.

    A question passes when its top score is at or above the cutoff, as in answer_question.
    """
    if not answerable_top or not unanswerable_top:
        raise ValueError("balanced accuracy needs both answerable and unanswerable scores")
    passed = sum(score >= cutoff for score in answerable_top) / len(answerable_top)
    refused = sum(score < cutoff for score in unanswerable_top) / len(unanswerable_top)
    return (passed + refused) / 2


def best_cutoff(answerable_top: list[float], unanswerable_top: list[float]) -> float:
    """The midpoint between consecutive distinct scores with the highest balanced accuracy.

    On a tie, the lowest such cutoff wins.
    """
    scores = sorted(set(answerable_top) | set(unanswerable_top))
    if len(scores) < 2:
        raise ValueError("need at least two distinct scores to place a cutoff")
    candidates = [(low + high) / 2 for low, high in zip(scores, scores[1:], strict=False)]
    best = max(balanced_accuracy(answerable_top, unanswerable_top, c) for c in candidates)
    return next(
        c for c in candidates if balanced_accuracy(answerable_top, unanswerable_top, c) == best
    )


def exact_mcnemar(only_first: int, only_second: int) -> float:
    """Two-sided exact McNemar p-value for two configurations judged on the same questions.

    Only the questions where they disagree count: the chance, were neither better, of those
    splitting at least this unevenly.
    """
    disagreements = only_first + only_second
    if disagreements == 0:
        return 1.0
    smaller = min(only_first, only_second)
    tail = sum(math.comb(disagreements, i) for i in range(smaller + 1)) / 2**disagreements
    return min(1.0, 2 * tail)


def _dcg(gains: list[int]) -> float:
    return sum(gain / math.log2(rank + 1) for rank, gain in enumerate(gains, start=1))


def _require_gold(gold: tuple[Gold, ...]) -> None:
    if not gold:
        raise ValueError("metrics need at least one gold entry")
