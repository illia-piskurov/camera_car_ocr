from __future__ import annotations

import re
from dataclasses import dataclass

NON_ALNUM = re.compile(r"[^A-Z0-9]")

# Keep fuzzy mapping explicit and limited. Disable by default in settings.
FUZZY_MAP = str.maketrans(
    {
        "O": "0",
        "Q": "0",
        "B": "8",
        "S": "5",
        "I": "1",
        "L": "1",
        "Z": "2",
    }
)


@dataclass(frozen=True)
class NormalizedPlate:
    normalized: str
    fuzzy: str


def normalize_plate(value: str) -> NormalizedPlate:
    normalized = NON_ALNUM.sub("", value.strip().upper())
    fuzzy = normalized.translate(FUZZY_MAP)
    return NormalizedPlate(normalized=normalized, fuzzy=fuzzy)
