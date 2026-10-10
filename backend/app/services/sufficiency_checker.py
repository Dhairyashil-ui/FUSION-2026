"""FUSION 2026 - Generic Geospatial Sufficiency Checker.

Evaluates whether a merged QueryUnderstanding state contains all 5 required dimensions:
1. WHAT: What the user wants to analyze/do (analytical task).
2. WHERE: Area of Interest (AOI) / geographic location.
3. TARGET: Target entities, objects, or spatial features under investigation.
4. MEASUREMENT: Spatial relationships, constraints, filters and operations.
5. OUTPUT FORMAT: Compulsory requested result artifact (e.g. map, report, statistics, GeoJSON).

READY is allowed ONLY when all 5 fields are sufficiently defined.
100% domain-agnostic across arbitrary GeoAI queries.
"""

import logging
from typing import List
from app.schemas.query_schema import QueryUnderstanding
from app.schemas.sufficiency_schema import (
    SufficiencyResult,
    KnownInformation,
    SufficiencyStatus,
)

logger = logging.getLogger(__name__)

# Generic non-informative / vague analytical goals
VAGUE_WHAT_TERMS = {
    "something", "anything", "stuff", "unclear", "unknown",
    "general analysis", "something in", "analyze something",
    "general", "undefined", "none"
}


class SufficiencyChecker:
    """
    Evaluates query sufficiency across all 5 compulsory geospatial dimensions
    strictly based on the cumulative merged state.
    """

    def check(self, understanding: QueryUnderstanding) -> SufficiencyResult:
        """
        Evaluates query sufficiency on the MERGED state.
        Requires all 5 fields (WHAT, WHERE, TARGET, MEASUREMENT, OUTPUT FORMAT) to be defined.

        Args:
            understanding: 5-field QueryUnderstanding model (cumulative merged state).

        Returns:
            SufficiencyResult: Detailed readiness state and targeted questions for missing fields.
        """
        # 1. WHAT (Analytical intent / problem)
        what_val = (understanding.what.value or "").strip()
        what_lower = what_val.lower()
        is_what_vague = (
            not what_val
            or what_lower in VAGUE_WHAT_TERMS
            or any(vague in what_lower for vague in ["something", "unclear"])
            or understanding.what.confidence < 0.3
        )
        what_known = not is_what_vague

        # 2. WHERE (Area of Interest / AOI)
        where_val = (understanding.where.value or "").strip()
        is_global = where_val.upper() in ("GLOBAL", "WORLDWIDE", "EARTH")
        where_known = bool(where_val) or is_global

        # 3. TARGET (Target entities / features)
        target_known = bool(understanding.target.values and len(understanding.target.values) > 0)

        # 4. MEASUREMENT (Spatial relationships, constraints, filters and operations)
        measurement_val = (understanding.measurement.value or "").strip()
        measurement_known = bool(measurement_val) or (understanding.measurement.confidence > 0.0 and understanding.measurement.provided_by_user)

        # 5. OUTPUT FORMAT (Compulsory requested result format)
        output_format_known = bool(understanding.output_format.values and len(understanding.output_format.values) > 0)

        known_info = KnownInformation(
            what=what_known,
            where=where_known,
            target=target_known,
            measurement=measurement_known,
            output_format=output_format_known,
        )

        missing_fields: List[str] = []
        questions: List[str] = []

        # =========================================================================
        # PRIORITY 1: WHAT
        # If the analytical objective is missing/unclear, ask for WHAT first.
        # =========================================================================
        if not what_known:
            missing_fields.append("what")
            if where_known and not is_global:
                questions.append(f"What would you like me to analyze in {where_val}?")
            else:
                questions.append("What would you like to analyze?")

            return SufficiencyResult(
                status="NEEDS_INFORMATION",
                is_sufficient=False,
                known_information=known_info,
                missing_information=missing_fields,
                questions_for_user=questions,
                reason="The analytical objective is required before determining other requirements."
            )

        # =========================================================================
        # PRIORITY 2: WHERE
        # =========================================================================
        if not where_known:
            missing_fields.append("where")
            questions.append("Which area should I analyze?")

        # =========================================================================
        # PRIORITY 3: TARGET
        # =========================================================================
        if not target_known:
            missing_fields.append("target")
            questions.append("Which target entities or spatial features would you like to find?")

        # =========================================================================
        # PRIORITY 4: MEASUREMENT
        # =========================================================================
        if not measurement_known:
            missing_fields.append("measurement")
            questions.append("What spatial relationships, constraints, filters, or operations should be applied?")

        # =========================================================================
        # PRIORITY 5: OUTPUT FORMAT (Compulsory)
        # =========================================================================
        if not output_format_known:
            missing_fields.append("output_format")
            questions.append("What output format would you like to receive (e.g. map, report, statistics, GeoJSON)?")

        is_sufficient = len(missing_fields) == 0
        status: SufficiencyStatus = "READY" if is_sufficient else "NEEDS_INFORMATION"

        if is_sufficient:
            reason = "All 5 required analytical dimensions (what, where, target, measurement, output format) are sufficiently defined."
        else:
            reason = f"Missing required dimensions: {', '.join(missing_fields)}."

        logger.info(f"Sufficiency check complete: status={status}, missing={missing_fields}")

        return SufficiencyResult(
            status=status,
            is_sufficient=is_sufficient,
            known_information=known_info,
            missing_information=missing_fields,
            questions_for_user=questions,
            reason=reason
        )


# Singleton instance
sufficiency_checker = SufficiencyChecker()
