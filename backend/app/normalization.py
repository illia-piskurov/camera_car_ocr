from __future__ import annotations

import re
from dataclasses import dataclass

NON_ALNUM = re.compile(r"[^A-Z0-9]")

# UA/CIS plates often come with Cyrillic letters that are visually identical to Latin.
# Convert them before filtering so values from 1C (e.g., "ВМ0756АХ") stay matchable.
CYRILLIC_TO_LATIN = str.maketrans(
    {
        "А": "A",
        "В": "B",
        "Е": "E",
        "І": "I",
        "К": "K",
        "М": "M",
        "Н": "H",
        "О": "O",
        "Р": "P",
        "С": "C",
        "Т": "T",
        "У": "Y",
        "Х": "X",
    }
)

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
    canonical = value.strip().upper().translate(CYRILLIC_TO_LATIN)
    normalized = NON_ALNUM.sub("", canonical)
    fuzzy = normalized.translate(FUZZY_MAP)
    return NormalizedPlate(normalized=normalized, fuzzy=fuzzy)
