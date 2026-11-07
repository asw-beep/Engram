"""Include patterns for repository paths: ** crosses folders, * and ? stay within one."""

import re
from functools import lru_cache


def matches_include(path: str, patterns: list[str]) -> bool:
    return any(_compile(pattern).fullmatch(path) for pattern in patterns)


@lru_cache(maxsize=256)
def _compile(pattern: str) -> re.Pattern[str]:
    # A trailing slash means everything under that folder, as in .gitignore.
    if pattern.endswith("/"):
        pattern += "**"
    parts: list[str] = []
    position = 0
    while position < len(pattern):
        if pattern.startswith("**/", position):
            parts.append("(?:.*/)?")
            position += 3
        elif pattern.startswith("**", position):
            parts.append(".*")
            position += 2
        elif pattern[position] == "*":
            parts.append("[^/]*")
            position += 1
        elif pattern[position] == "?":
            parts.append("[^/]")
            position += 1
        else:
            parts.append(re.escape(pattern[position]))
            position += 1
    return re.compile("".join(parts))
