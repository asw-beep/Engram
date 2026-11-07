from collections.abc import Callable

from app.types import Passage


def select_passages(
    passages: list[Passage],
    count_tokens: Callable[[str], int],
    max_passages: int,
    max_context_tokens: int,
) -> list[Passage]:
    """Keep passages in rank order, without repeats, up to a count and a token budget.

    A passage too large for the remaining budget is skipped, so smaller ones after it can
    still fit.
    """
    picked: list[Passage] = []
    seen: set[str] = set()
    used = 0
    for passage in passages:
        if len(picked) == max_passages:
            break
        key = " ".join(passage.content.lower().split())
        if key in seen:
            continue
        tokens = count_tokens(passage.content)
        if used + tokens > max_context_tokens:
            continue
        seen.add(key)
        picked.append(passage)
        used += tokens
    return picked
