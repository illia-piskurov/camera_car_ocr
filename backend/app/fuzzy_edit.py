"""Edit-distance based fuzzy plate matching.

Compares a recognized plate against all whitelist plates and returns the
closest match if it is within the configured Levenshtein distance limit.
"""

from __future__ import annotations


def levenshtein_bounded(a: str, b: str, max_dist: int) -> int:
    """Levenshtein distance capped at max_dist+1 for early termination."""
    if abs(len(a) - len(b)) > max_dist:
        return max_dist + 1

    m, n = len(a), len(b)
    prev = list(range(n + 1))

    for i in range(1, m + 1):
        curr = [i] + [0] * n
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1]
            else:
                curr[j] = 1 + min(prev[j], curr[j - 1], prev[j - 1])
        prev = curr
        if min(prev) > max_dist:
            return max_dist + 1

    return prev[n]


def find_best_edit_match(
    plate: str,
    candidates: list[str],
    max_dist: int,
) -> tuple[str | None, int]:
    """Return (closest_whitelist_plate, distance) or (None, max_dist+1) if no match.

    Iterates all active whitelist plates and picks the one with the smallest
    Levenshtein distance. Ties broken by first encountered.
    """
    best_plate: str | None = None
    best_dist = max_dist + 1

    for candidate in candidates:
        dist = levenshtein_bounded(plate, candidate, max_dist)
        if dist <= max_dist and dist < best_dist:
            best_dist = dist
            best_plate = candidate
            if dist == 0:
                break

    return best_plate, best_dist
