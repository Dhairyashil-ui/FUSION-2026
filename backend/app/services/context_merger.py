"""FUSION 2026 - Generic Geospatial Context Merger.

Merges newly extracted user message components with the previous conversation state.
Applies domain-agnostic rules:
1. Preserve previously established dimensions when unchanged.
2. Incorporate newly provided dimensions.
3. Replace dimensions when explicitly updated or corrected.
4. Support target entity and output format accumulation vs replacement.
5. Never invent or default unstated information.
"""

import logging
from typing import Optional, List
from app.schemas.query_schema import (
    QueryUnderstanding,
    WhatSchema,
    WhereSchema,
    TargetSchema,
    MeasurementSchema,
    OutputFormatSchema,
)

logger = logging.getLogger(__name__)

# Generic linguistic cues for replacement vs accumulation
REPLACEMENT_INDICATORS = {
    "only", "instead", "just", "replace", "forget", "exclude", "drop",
    "change to", "switch to", "not", "rather than", "actually", "focus on"
}

ACCUMULATION_INDICATORS = {
    "also", "and", "add", "as well", "include", "including", "plus",
    "along with", "together with", "in addition"
}


class ContextMerger:
    """
    Coordinates multi-turn state preservation and updates across
    arbitrary geospatial queries.
    """

    def merge(
        self,
        previous: Optional[QueryUnderstanding],
        current: QueryUnderstanding,
        user_message: str = ""
    ) -> QueryUnderstanding:
        """
        Merges current extraction into previous state.

        Args:
            previous: The accumulated QueryUnderstanding state from prior turns (or None).
            current: The newly extracted QueryUnderstanding from the current message.
            user_message: Raw user query string for nuance disambiguation (e.g. accumulation cues).

        Returns:
            QueryUnderstanding: The unified merged state.
        """
        if previous is None:
            return current

        msg_lower = (user_message or "").lower()

        merged_what = self._merge_what(previous.what, current.what, msg_lower)
        merged_where = self._merge_where(previous.where, current.where, msg_lower)
        merged_target = self._merge_target(previous.target, current.target, msg_lower)
        merged_measurement = self._merge_measurement(previous.measurement, current.measurement, msg_lower)
        merged_output_format = self._merge_output_format(previous.output_format, current.output_format, msg_lower)

        merged = QueryUnderstanding(
            what=merged_what,
            where=merged_where,
            target=merged_target,
            measurement=merged_measurement,
            output_format=merged_output_format
        )

        logger.debug(
            f"Merged state: what='{merged.what.value}', where='{merged.where.value}', "
            f"measurement='{merged.measurement.value}', targets={merged.target.values}, "
            f"formats={merged.output_format.values}"
        )
        return merged


    def _merge_what(self, prev: WhatSchema, curr: WhatSchema, msg_lower: str) -> WhatSchema:
        """
        Merges WHAT (Analytical intent).
        Preserves previous WHAT unless current message explicitly provides or corrects it.
        """
        prev_has_what = bool(prev.value and prev.value.strip())
        curr_has_what = bool(curr.value and curr.value.strip())

        if not prev_has_what:
            return curr if curr_has_what else prev

        if not curr_has_what:
            return prev

        is_explicit_replace = any(word in msg_lower for word in REPLACEMENT_INDICATORS)
        if is_explicit_replace:
            return curr

        prev_val_lower = prev.value.lower()
        curr_val_lower = curr.value.lower()

        if curr_val_lower == prev_val_lower or curr_val_lower in prev_val_lower:
            return prev

        if prev_val_lower in curr_val_lower:
            return curr

        is_accumulate = any(word in msg_lower for word in ACCUMULATION_INDICATORS)
        analytical_verbs = {"analyze", "analysis", "detect", "detection", "monitor", "monitoring", "change", "assess", "assessment", "predict", "prediction", "estimate", "classify", "study", "growth", "loss", "expansion", "damage", "severity", "bleaching", "deforestation", "flood", "inundation", "fire"}
        curr_has_analytical_intent = any(verb in curr_val_lower for verb in analytical_verbs)
        if is_accumulate and not curr_has_analytical_intent:
            return prev

        return curr

    def _merge_where(self, prev: WhereSchema, curr: WhereSchema, msg_lower: str) -> WhereSchema:
        """
        Merges WHERE (Area of Interest / AOI).
        Preserves previous AOI unless a new location is provided or explicitly changed.
        """
        prev_has_where = bool(prev.value and prev.value.strip())
        curr_has_where = bool(curr.value and curr.value.strip())

        if not prev_has_where:
            return curr if curr_has_where else prev

        if not curr_has_where:
            return prev

        is_accumulate = any(word in msg_lower for word in ACCUMULATION_INDICATORS)
        if is_accumulate and prev.value.lower() != curr.value.lower():
            if curr.value.lower() not in prev.value.lower():
                return WhereSchema(
                    value=f"{prev.value}, {curr.value}",
                    type=curr.type or prev.type,
                    confidence=max(prev.confidence, curr.confidence),
                    provided_by_user=True
                )
            return prev

        return curr

    def _merge_measurement(self, prev: MeasurementSchema, curr: MeasurementSchema, msg_lower: str) -> MeasurementSchema:
        """
        Merges MEASUREMENT (Spatial relationships, constraints, filters and operations).
        Preserves previous measurement constraints unless current turn provides new or updated measurements.
        """
        prev_has_meas = bool(prev.value and prev.value.strip())
        curr_has_meas = bool(curr.value and curr.value.strip())

        if not prev_has_meas:
            return curr if curr_has_meas else prev

        if not curr_has_meas:
            return prev

        is_replace = any(word in msg_lower for word in REPLACEMENT_INDICATORS)
        if is_replace:
            return curr

        # If user provides new measurement details, append or refine
        if curr.value and curr.value.lower() not in prev.value.lower():
            merged_val = f"{prev.value}; {curr.value}"
            return MeasurementSchema(
                value=merged_val,
                confidence=max(prev.confidence, curr.confidence),
                provided_by_user=True
            )

        return prev

    def _merge_target(self, prev: TargetSchema, curr: TargetSchema, msg_lower: str) -> TargetSchema:
        """
        Merges TARGET entities.
        Handles accumulation (also, and, include) vs explicit replacement (only, instead).
        """
        prev_has_targets = bool(prev.values and len(prev.values) > 0)
        curr_has_targets = bool(curr.values and len(curr.values) > 0)

        if not prev_has_targets:
            return curr if curr_has_targets else prev

        if not curr_has_targets:
            return prev

        is_replace = any(ind in msg_lower for ind in ["only", "instead", "just", "replace", "forget", "drop", "exclude", "rather than", "switch to"])

        if is_replace:
            return curr

        merged_values: List[str] = list(prev.values)
        existing_lower = {v.lower() for v in merged_values}

        for item in curr.values:
            if item.lower() not in existing_lower:
                merged_values.append(item)
                existing_lower.add(item.lower())

        return TargetSchema(
            values=merged_values,
            confidence=max(prev.confidence, curr.confidence),
            provided_by_user=True
        )

    def _merge_output_format(self, prev: OutputFormatSchema, curr: OutputFormatSchema, msg_lower: str) -> OutputFormatSchema:
        """
        Merges OUTPUT FORMAT.
        Preserves requested formats.
        """
        prev_has_formats = bool(prev.values and len(prev.values) > 0)
        curr_has_formats = bool(curr.values and len(curr.values) > 0)

        if not prev_has_formats:
            return curr if curr_has_formats else prev

        if not curr_has_formats:
            return prev

        is_replace = any(ind in msg_lower for ind in ["only", "instead", "just", "replace", "forget", "drop"])
        if is_replace:
            return curr

        merged_values: List[str] = list(prev.values)
        existing_lower = {v.lower() for v in merged_values}

        for item in curr.values:
            if item.lower() not in existing_lower:
                merged_values.append(item)
                existing_lower.add(item.lower())

        return OutputFormatSchema(
            values=merged_values,
            confidence=max(prev.confidence, curr.confidence),
            provided_by_user=True
        )


# Singleton instance
context_merger = ContextMerger()
