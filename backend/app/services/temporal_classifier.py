"""FUSION 2026 - Generic Geospatial Temporal Classification Engine.

Classifies temporal expressions and queries into exactly four modes:
- PAST: historical dates, past years, previous/completed events, completed periods.
- REAL_TIME: current, live, ongoing, streaming, right now.
- FUTURE: predictions, forecasts, upcoming, projections, future dates/periods.
- UNKNOWN: no temporal information expressed.

Domain-agnostic: relies on temporal semantics, calendar dates, numeric years, and grammatical tense markers.
Zero hardcoded domain or disaster rules.
"""

import re
from typing import Optional, Tuple
from app.schemas.query_schema import WhenSchema

# Reference current year
CURRENT_YEAR = 2026

# Real-time patterns (live / current monitoring)
REAL_TIME_REGEX = re.compile(
    r"\b(?:real[- ]?time|live|right now|currently|current|ongoing|streaming|continuous(?:ly)?|at present|presently|active stream)\b",
    re.IGNORECASE
)

# Future patterns (predictive / forecast)
FUTURE_REGEX = re.compile(
    r"\b(?:predict(?:ion|ive|ing|ed)?|forecast(?:ing|s|ed)?|project(?:ion|ed|ing|s)?|future|upcoming|tomorrow|next (?:week|month|year|decade)|ahead|expected|scenario)\b",
    re.IGNORECASE
)

# Explicit past indicators (historical / completed)
PAST_REGEX = re.compile(
    r"\b(?:yesterday|last (?:week|month|year|decade)|historical|historic|previously|previous|prior|archived|recorded|former|earlier|ago|back in|post[- ]|after the|latest|recent)\b",
    re.IGNORECASE
)

# Year detection regex (4-digit years between 1800 and 2100)
YEAR_REGEX = re.compile(r"\b(1[89]\d\d|20\d\d|2100)\b")


class TemporalClassifier:
    """
    Evaluates and normalizes temporal information into:
    PAST, REAL_TIME, FUTURE, or UNKNOWN.
    """

    def classify(self, when: WhenSchema, raw_query: str = "") -> WhenSchema:
        """
        Normalizes and classifies a WhenSchema instance using both
        the schema's fields and the raw user query context.

        Args:
            when: Initial WhenSchema instance (e.g. from LLM extraction).
            raw_query: Raw natural language query from user.

        Returns:
            WhenSchema with strictly verified temporal_mode and flags.
        """
        text_to_analyze = " ".join(filter(None, [
            raw_query,
            when.time_period,
            when.event,
            when.start,
            when.end,
        ])).strip()

        mode = self.determine_mode(text_to_analyze, initial_mode=when.temporal_mode)

        # Determine provided_by_user
        has_temporal_data = bool(
            when.time_period or when.event or when.start or when.end or (mode != "UNKNOWN")
        )

        # If mode is UNKNOWN and no temporal fields exist, confidence is 0.0 unless specified
        confidence = when.confidence
        if mode == "UNKNOWN" and not (when.time_period or when.event or when.start or when.end):
            provided = False
            confidence = 0.0
        else:
            provided = when.provided_by_user or (mode != "UNKNOWN")
            confidence = max(confidence, 0.9) if provided else 0.0

        return WhenSchema(
            temporal_mode=mode,
            time_period=when.time_period,
            start=when.start,
            end=when.end,
            event=when.event,
            confidence=confidence,
            provided_by_user=provided
        )

    def determine_mode(self, text: str, initial_mode: str = "UNKNOWN") -> str:
        """
        Determines the temporal mode (PAST, REAL_TIME, FUTURE, UNKNOWN)
        from text content and numeric years.
        """
        if not text or not text.strip():
            return "UNKNOWN"

        text_lower = text.lower()

        # 1. Check for REAL_TIME signals
        # Note: 'latest' or 'recent' refers to PAST completed events, not REAL_TIME
        if REAL_TIME_REGEX.search(text_lower):
            # Verify it's not a past context like "last year currently archived"
            return "REAL_TIME"

        # 2. Check for FUTURE signals
        if FUTURE_REGEX.search(text_lower):
            return "FUTURE"

        # 3. Check for 4-digit years
        years = [int(y) for y in YEAR_REGEX.findall(text)]
        if years:
            # If any year is in the future (> CURRENT_YEAR)
            if any(y > CURRENT_YEAR for y in years):
                return "FUTURE"
            # If all years are past/current (<= CURRENT_YEAR)
            return "PAST"

        # 4. Check for explicit PAST keywords
        if PAST_REGEX.search(text_lower):
            return "PAST"

        # 5. Respect initial_mode if valid and not UNKNOWN
        if initial_mode in ("PAST", "REAL_TIME", "FUTURE"):
            return initial_mode

        return "UNKNOWN"


temporal_classifier = TemporalClassifier()
