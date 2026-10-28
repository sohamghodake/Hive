"""Small helpers shared by the eval scripts."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"


def pct(values: list[float], p: float) -> float:
    """Nearest-rank percentile; enough for tens to hundreds of samples."""
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(p / 100 * (len(ordered) - 1))))]


_UNICODE_PUNCT = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    # Models often write non-breaking or typographic hyphens ("thirty‑six").
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
    " ": " ", " ": " ",
})


def norm(text: str) -> str:
    """Lowercase, unify quotes, dashes and spaces, collapse whitespace — for substring matching."""
    return re.sub(r"\s+", " ", text.translate(_UNICODE_PUNCT)).strip().lower()


def save(name: str, payload: dict) -> Path:
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / name
    payload = {"measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **payload}
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path
