"""Person names (sign-up). Letters in any script — Latin, Devanagari (with its vowel signs) and
others — plus spaces and the joiners people actually use: . ' ’ -. No digits, no symbols."""

import unicodedata

JOINERS = set(" .'’-")


def clean_full_name(raw: str) -> str | None:
    """The name with spaces tidied, or None if it isn't a plausible name."""
    name = " ".join(raw.split())
    if not 2 <= len(name) <= 120:
        return None
    letters = 0
    for ch in name:
        category = unicodedata.category(ch)
        if category.startswith("L"):
            letters += 1
        elif category.startswith("M") or ch in JOINERS:  # M: Devanagari matras, nukta, virama
            continue
        else:  # digits (N*), symbols (S*), other punctuation
            return None
    return name if letters >= 2 and unicodedata.category(name[0]).startswith("L") else None
