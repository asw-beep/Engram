"""Reciprocal Rank Fusion (spec section 5): merge rankings by position, not by score.

Dense and BM25 scores are on different scales, so only each chunk's rank in each list counts.
"""

from uuid import UUID


def reciprocal_rank_fusion(rankings: list[list[UUID]], k: int = 60) -> list[tuple[UUID, float]]:
    """Score each ID as the sum of 1 / (k + rank) over the rankings holding it, rank from 1.

    Highest score first. A tie goes to the ID met first, reading the rankings in order.
    """
    scores: dict[UUID, float] = {}
    for ranking in rankings:
        seen: set[UUID] = set()
        for rank, chunk_id in enumerate(ranking, start=1):
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    first_met = {chunk_id: order for order, chunk_id in enumerate(scores)}
    return sorted(scores.items(), key=lambda item: (-item[1], first_met[item[0]]))
