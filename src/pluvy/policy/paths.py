"""Repository-relative path matching and directory scope decisions shared by policy consumers."""

from fnmatch import fnmatchcase


def matches(value: str, patterns: tuple[str, ...]) -> bool:
    """Use case-sensitive shell patterns; stars may span path separators."""
    return any(fnmatchcase(value, pattern) for pattern in patterns)


def prunable(directory: str, include: tuple[str, ...], exclude: tuple[str, ...]) -> bool:
    """Report whether the policy can select no file anywhere below ``directory``.

    ``True`` guarantees that no file under ``directory`` satisfies ``matches``
    against ``include`` while escaping ``exclude``, so a caller may skip
    enumerating it. ``False`` only means such a file may still exist and never
    authorizes skipping.

    Each pattern is compared through its head: the leading characters that
    must line up with the directory prefix one for one, where ``?`` matches
    any single character. The head stops at the first ``*``, at the first
    ``[`` or at the end of the directory prefix, whichever comes first; the
    rest is the tail.

    An include pattern cannot reach the directory when its head mismatches or
    its tail is empty (the pattern ended without reaching a star). Otherwise
    the directory stays reachable and the tail is only checked to be
    non-empty, so ``src/[v]endor/*`` cannot reach ``docs`` yet keeps
    ``src/vendor``, and ``src/*/`` keeps ``src`` although file paths never end
    with a slash.

    An exclude pattern covers the directory only when its head matches and its
    tail consists solely of stars (one or more), as in ``dir/*``, ``dir/**`` or
    ``**``. A pattern containing ``[`` or a structured tail such as ``src/*.py``
    or ``src/*/*`` never prunes. Common patterns, including the default ``**``,
    keep their exact result.
    """
    stem = f"{directory}/"
    return not any(_reaches(stem, pattern) for pattern in include) or any(
        _covers(stem, pattern) for pattern in exclude
    )


def _head(pattern: str, width: int) -> tuple[str, str]:
    """Split a pattern before its first star or bracket, bounded by the stem width."""
    index = 0
    while index < len(pattern) and index < width and pattern[index] not in "*[":
        index += 1
    return pattern[:index], pattern[index:]


def _reaches(stem: str, pattern: str) -> bool:
    """Report whether an include pattern can still match a file below the stem."""
    head, tail = _head(pattern, len(stem))
    return bool(tail) and fnmatchcase(stem[: len(head)], head)


def _covers(stem: str, pattern: str) -> bool:
    """Report whether an exclude pattern covers every file below the stem."""
    head, tail = _head(pattern, len(stem))
    return bool(tail) and tail.strip("*") == "" and fnmatchcase(stem[: len(head)], head)
