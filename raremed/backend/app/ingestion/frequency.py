"""Preserve source frequency strings and normalize only recognized bands."""

from __future__ import annotations

import re

from app.ingestion.identifiers import parse_identifier

HPO_FREQUENCY = {
    "HP:0040280": "obligate",
    "HP:0040281": "very_frequent",
    "HP:0040282": "frequent",
    "HP:0040283": "occasional",
    "HP:0040284": "very_rare",
    "HP:0040285": "excluded",
}

TEXT_BANDS = (
    (re.compile(r"\bobligate\b|100\s*%", re.I), "obligate"),
    (re.compile(r"very\s+frequent|99\s*[-–]\s*80|80\s*[-–]\s*99", re.I), "very_frequent"),
    (re.compile(r"\bfrequent\b|79\s*[-–]\s*30|30\s*[-–]\s*79", re.I), "frequent"),
    (re.compile(r"\boccasional\b|29\s*[-–]\s*5|5\s*[-–]\s*29", re.I), "occasional"),
    (re.compile(r"very\s+rare|4\s*[-–]\s*1|1\s*[-–]\s*4", re.I), "very_rare"),
    (re.compile(r"\bexcluded\b|0\s*%", re.I), "excluded"),
)

FRACTION = re.compile(r"^(\d+)\s*/\s*(\d+)$")
PERCENT = re.compile(r"^(\d+(?:\.\d+)?)\s*%$")


def normalize_frequency(raw: str | None) -> tuple[str | None, str | None]:
    """Return (original, normalized_band_or_none). Never invent a band."""
    if raw is None:
        return None, None
    text = raw.strip()
    if not text:
        return None, None

    identifier = parse_identifier(text)
    if identifier and identifier.curie in HPO_FREQUENCY:
        return text, HPO_FREQUENCY[identifier.curie]

    for pattern, band in TEXT_BANDS:
        if pattern.search(text):
            return text, band

    if FRACTION.match(text) or PERCENT.match(text):
        return text, None
    return text, None


def polarity_from(*, qualifier: str | None, frequency_normalized: str | None) -> str:
    token = (qualifier or "").strip().upper()
    if token in {"NOT", "ABSENT", "EXCLUDED"}:
        return "absent"
    if frequency_normalized == "excluded":
        return "absent"
    return "present"
