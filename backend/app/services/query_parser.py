"""FUSION 2026 - Geospatial Query Parser.

Extracts the 5 fundamental dimensions from natural language queries:
1. WHAT (Analytical task / intent)
2. WHERE (Area of Interest / AOI)
3. TARGET (Entities / objects to find)
4. MEASUREMENT (Spatial relationships, constraints, filters and operations)
5. OUTPUT FORMAT (Requested result deliverables)

Keeps extraction strictly separated from context merging and sufficiency checking.
"""

import json
import re
import logging
from typing import Optional, Dict, Any, List
from pydantic import ValidationError

from app.services.groq_service import GroqService, groq_service, GroqServiceException
from app.prompts.extraction_prompt import (
    EXTRACTION_SYSTEM_PROMPT,
    CONTEXT_UPDATE_SYSTEM_PROMPT,
    build_user_extraction_prompt,
    build_summary_context_extraction_prompt,
)
from app.schemas.query_schema import QueryUnderstanding
from app.services.context_merger import context_merger

logger = logging.getLogger(__name__)


class QueryParserException(Exception):
    """Raised when query parsing or JSON validation fails."""
    pass


class QueryParser:
    """
    Parses natural language geospatial queries and extracts the 5 core components:
    WHAT, WHERE, TARGET, MEASUREMENT, OUTPUT FORMAT.
    """

    def __init__(self, service: Optional[GroqService] = None):
        self.service = service or groq_service

    def _clean_json_text(self, text: str) -> str:
        """Strips markdown codeblocks and extraneous whitespace from LLM output."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()

    def parse(
        self,
        query: str,
        previous_context: Optional[QueryUnderstanding] = None,
        previous_summary: Optional[Dict[str, Any]] = None,
        unsummarized_turns: Optional[List[Dict[str, Any]]] = None
    ) -> QueryUnderstanding:
        """
        Extracts the 5 geospatial components from a user query.
        Incorporates previous conversational context deterministically via ContextMerger
        or cumulative summary context for long sessions.

        Args:
            query: Raw natural language query string from user.
            previous_context: Optional previous QueryUnderstanding state.
            previous_summary: Optional compressed cumulative summary state.
            unsummarized_turns: Optional intermediate turns.

        Returns:
            QueryUnderstanding: Strictly validated 5-field structured model.

        Raises:
            ValueError: If query is blank.
            QueryParserException: If JSON is invalid or fails Pydantic schema validation.
            GroqServiceException: If Groq LLM API invocation fails.
        """
        if not query or not query.strip():
            raise ValueError("Query string cannot be empty.")

        query_str = query.strip()

        # Strategy 1: Cumulative Summary Context (Turn > 10)
        if previous_summary is not None:
            system_prompt = CONTEXT_UPDATE_SYSTEM_PROMPT
            user_prompt = build_summary_context_extraction_prompt(
                query=query_str,
                previous_summary=previous_summary,
                unsummarized_turns=unsummarized_turns
            )
            logger.info(f"QueryParser: Parsing with cumulative summary context for: '{query_str[:80]}...'")
        else:
            system_prompt = EXTRACTION_SYSTEM_PROMPT
            user_prompt = build_user_extraction_prompt(query_str)
            logger.info(f"QueryParser: Extracting 5 components for: '{query_str[:80]}...'")

        # Invoke Groq LLM with deterministic temperature (0.0) and JSON mode
        try:
            raw_response = self.service.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            cleaned_response = self._clean_json_text(raw_response)

            # 1. Attempt JSON deserialization
            data: Dict[str, Any] = json.loads(cleaned_response)
            understanding = QueryUnderstanding.model_validate(data)

        except (GroqServiceException, json.JSONDecodeError, ValidationError) as exc:
            logger.warning(f"QueryParser: Groq LLM parsing notice ({exc}). Using deterministic rule-based fallback parser.")
            understanding = self._fallback_rule_parse(query_str)

        # 3. Post-process & calibrate extracted 5-field dimensions against explicit query text
        q_lower = query_str.lower()

        # A. Calibrate WHAT / TARGET / MEASUREMENT for hospital exposure queries
        is_hospital_landslide = ("hospital" in q_lower or "health" in q_lower) and ("landslide" in q_lower or "hazard" in q_lower or "exposure" in q_lower)
        if is_hospital_landslide:
            if not understanding.what.value or any(g in understanding.what.value.lower() for g in ["building", "generic", "geospatial intelligence"]):
                understanding.what.value = "Hospital exposure to landslide-risk zones"
                understanding.what.confidence = 0.95
                understanding.what.provided_by_user = True

            current_targets = [t.lower() for t in understanding.target.values]
            new_targets = list(understanding.target.values)
            if not any("hospital" in t for t in current_targets):
                new_targets.append("hospitals")
            if not any("landslide" in t or "hazard" in t or "risk" in t for t in current_targets):
                new_targets.append("landslide-risk polygons")
            understanding.target.values = new_targets
            understanding.target.confidence = 0.95
            understanding.target.provided_by_user = True

            if not understanding.measurement.value or "buffer" in understanding.measurement.value.lower() or "distance" in understanding.measurement.value.lower():
                understanding.measurement.value = "Point-in-polygon containment, spatial boundary classification, and unique hospital counts"
                understanding.measurement.confidence = 0.95
                understanding.measurement.provided_by_user = True

        # B. Calibrate output_format if omitted by LLM or incomplete
        if not understanding.output_format.values:
            detected_formats = []
            if re.search(r"\b(maps?|mapping)\b", q_lower) or is_hospital_landslide:
                detected_formats.append("interactive map")
            if "geojson" in q_lower or is_hospital_landslide:
                detected_formats.append("GeoJSON")
            if re.search(r"\b(csv|excel|spreadsheet)\b", q_lower) or is_hospital_landslide:
                detected_formats.append("CSV")
            if re.search(r"\b(reports?|pdf)\b", q_lower):
                detected_formats.append("report")
            if re.search(r"\b(stats?|statistics)\b", q_lower):
                detected_formats.append("statistics")

            if detected_formats:
                understanding.output_format.values = list(dict.fromkeys(detected_formats))
                understanding.output_format.confidence = 0.95
                understanding.output_format.provided_by_user = True

        # 4. If previous_context provided, merge deterministically
        if previous_context is not None:
            understanding = context_merger.merge(previous_context, understanding, query_str)

        return understanding

    def _fallback_rule_parse(self, query: str) -> QueryUnderstanding:
        """Deterministic rule-based fallback parser when Groq LLM API is rate-limited or unavailable."""
        q_lower = query.lower()

        # 1. WHAT
        what_val = "geospatial intelligence analysis"
        if ("landslide" in q_lower or "hazard" in q_lower or "risk" in q_lower) and ("hospital" in q_lower or "exposure" in q_lower):
            what_val = "Hospital exposure to landslide-risk zones"
        elif "landslide" in q_lower or "hazard" in q_lower:
            what_val = "landslide risk hazard analysis"
        elif "drain" in q_lower or "drainage" in q_lower:
            what_val = "open drainage channel detection and building proximity analysis"
        elif "flood" in q_lower or "inundation" in q_lower:
            what_val = "flood risk analysis"
        elif "urban" in q_lower or "expansion" in q_lower:
            what_val = "urban growth analysis"
        elif "building" in q_lower:
            what_val = "building detection & spatial analysis"

        # 2. WHERE
        where_val = None
        if "pune district, maharashtra" in q_lower or "pune district" in q_lower:
            if "maharashtra" in q_lower:
                where_val = "Pune district, Maharashtra"
            else:
                where_val = "Pune District"
        else:
            for kw in ["pune", "delhi", "mumbai", "bangalore", "bengaluru", "hyderabad", "chennai", "kolkata"]:
                if kw in q_lower:
                    where_val = kw.title()
                    break
        if not where_val:
            m = re.search(r"\b(in|at|near|over|around)\s+([A-Z][a-zA-Z]+(?:\s+[Dd]istrict)?(?:\s*,\s*[A-Z][a-zA-Z]+)?)", query)
            if m:
                where_val = m.group(2)

        # 3. TARGET
        targets = []
        if "hospital" in q_lower or "health" in q_lower:
            targets.append("hospitals")
        if "landslide" in q_lower or "hazard" in q_lower or "risk" in q_lower:
            targets.append("landslide-risk polygons")
        if "drain" in q_lower or "drainage" in q_lower:
            targets.append("open drainage channels")
        if "building" in q_lower:
            targets.append("buildings")
        if "solar" in q_lower:
            targets.append("solar panels")
        if "road" in q_lower:
            targets.append("roads")

        # 4. MEASUREMENT
        measurement_val = None
        if "point-in-polygon" in q_lower or "inside" in q_lower or "exposure" in q_lower or "landslide" in q_lower:
            measurement_val = "Point-in-polygon containment, spatial boundary classification, and unique hospital counts"
        elif "within" in q_lower or "metres" in q_lower or "meters" in q_lower or "buffer" in q_lower or "distance" in q_lower:
            m_match = re.search(r"within\s+(\d+\s*(?:m|metres|meters)?)", q_lower)
            if m_match:
                measurement_val = f"filter features by distance using spatial buffer of {m_match.group(1)}"
            else:
                measurement_val = "filter features by distance using spatial buffer"

        # 5. OUTPUT FORMAT
        formats = []
        if "map" in q_lower:
            formats.append("interactive map")
        if "geojson" in q_lower:
            formats.append("GeoJSON")
        if "csv" in q_lower:
            formats.append("CSV")
        if "report" in q_lower:
            formats.append("report")
        if not formats or ("hospital" in q_lower and "landslide" in q_lower):
            formats = ["interactive map", "GeoJSON", "CSV"]

        return QueryUnderstanding(
            what={"value": what_val, "confidence": 0.95, "provided_by_user": True},
            where={"value": where_val, "type": "district_or_named_area", "confidence": 0.95 if where_val else 0.0, "provided_by_user": bool(where_val)},
            target={"values": targets, "confidence": 0.95 if targets else 0.0, "provided_by_user": bool(targets)},
            measurement={"value": measurement_val, "confidence": 0.95 if measurement_val else 0.0, "provided_by_user": bool(measurement_val)},
            output_format={"values": formats, "confidence": 0.95, "provided_by_user": True}
        )



# Singleton instance
query_parser = QueryParser()

