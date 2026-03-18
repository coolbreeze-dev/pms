from __future__ import annotations

import re


KNOWN_BROKERAGES = [
    "Wealthfront",
    "Fidelity",
    "Vanguard",
    "Schwab",
    "Empower",
    "Robinhood",
    "Principal",
    "Slavic 401k",
]

_BROKERAGE_ALIASES = {
    "wealthfront": "Wealthfront",
    "wealth front": "Wealthfront",
    "fidelity": "Fidelity",
    "fidelity investments": "Fidelity",
    "vanguard": "Vanguard",
    "charles schwab": "Schwab",
    "schwab": "Schwab",
    "empower": "Empower",
    "empower retirement": "Empower",
    "robinhood": "Robinhood",
    "robin hood": "Robinhood",
    "principal": "Principal",
    "principal financial": "Principal",
    "principal financial group": "Principal",
    "slavic": "Slavic 401k",
    "slavic 401k": "Slavic 401k",
    "slavic401k": "Slavic 401k",
}


def _clean_brokerage(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def normalize_brokerage(value: str) -> str:
    cleaned = _clean_brokerage(value)
    if not cleaned:
        return ""
    return _BROKERAGE_ALIASES.get(cleaned, value.strip())
