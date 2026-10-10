"""Pydantic schemas for FUSION-2026 Query Understanding and 5-field extraction."""
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator




class WhatSchema(BaseModel):
    """Answers: What does the user want us to analyze? (analytical problem/phenomenon)."""
    value: Optional[str] = Field(
        default=None,
        description="Analytical problem or phenomenon (e.g. flood analysis, urban change detection)"
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    provided_by_user: bool = Field(default=False)


class WhereSchema(BaseModel):
    """Answers: Where should the analysis happen? (Area of Interest / AOI)."""
    value: Optional[str] = Field(
        default=None,
        description="Named geographic location, bounding box, or polygon"
    )
    type: Optional[str] = Field(
        default=None,
        description="Type of location (e.g. city_or_named_area, state, country, polygon, bbox)"
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    provided_by_user: bool = Field(default=False)


class MeasurementSchema(BaseModel):
    """Answers: What spatial relationships, constraints, filters, thresholds, or operations should be applied?"""
    value: Optional[str] = Field(
        default=None,
        description="Spatial relationships, constraints, filters and operations (e.g. find buildings with solar panels and filter them by distance to drainage, using a 200 m threshold)"
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    provided_by_user: bool = Field(default=False)


class WhenSchema(BaseModel):
    """Answers: When should the analysis happen? (Temporal range / timeframe)."""
    value: Optional[str] = Field(
        default=None,
        description="Temporal range, date, or timeframe (e.g. 2024, January 2024, between 2020 and 2024, Latest available)"
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    provided_by_user: bool = Field(default=False)


class TargetSchema(BaseModel):
    """Answers: What objects/entities are we analyzing?"""
    values: List[str] = Field(
        default_factory=list,
        description="List of target objects/entities (e.g. buildings, hospitals, vehicles)"
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    provided_by_user: bool = Field(default=False)


class OutputFormatSchema(BaseModel):
    """Answers: What does the user want as the final result?"""
    values: List[str] = Field(
        default_factory=list,
        description="Requested output artifacts (e.g. map, statistics, CSV, report)"
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    provided_by_user: bool = Field(default=False)


class QueryUnderstanding(BaseModel):
    """Structured 5-field canonical query understanding representation (WHAT, WHERE, TARGET, MEASUREMENT, OUTPUT_FORMAT)."""
    what: WhatSchema = Field(default_factory=WhatSchema)
    where: WhereSchema = Field(default_factory=WhereSchema)
    target: TargetSchema = Field(default_factory=TargetSchema)
    measurement: MeasurementSchema = Field(default_factory=MeasurementSchema)
    output_format: OutputFormatSchema = Field(default_factory=OutputFormatSchema)

    def __init__(self, **data):
        when_val = data.pop("when", None)
        super().__init__(**data)
        if when_val is not None:
            self._when = when_val if isinstance(when_val, WhenSchema) else WhenSchema(value=str(when_val))
        else:
            self._when = WhenSchema(value=None, confidence=0.0, provided_by_user=False)

    @property
    def when(self) -> WhenSchema:
        return getattr(self, "_when", WhenSchema(value=None, confidence=0.0, provided_by_user=False))

    @when.setter
    def when(self, value):
        self._when = value if isinstance(value, WhenSchema) else WhenSchema(value=str(value) if value else None)

    @property
    def measurements(self) -> MeasurementSchema:
        return self.measurement

    @property
    def output(self) -> OutputFormatSchema:
        return self.output_format

    def model_dump(self, *args, **kwargs):
        d = super().model_dump(*args, **kwargs)
        # Ensure 5 dimensions are exposed cleanly
        d["measurements"] = d.get("measurement")
        d["output"] = d.get("output_format")
        return d




from uuid import UUID

class QueryParseRequest(BaseModel):
    """Incoming request for query parsing."""
    query: str = Field(..., min_length=1, description="Natural language geospatial query to parse")
    project_id: Optional[UUID] = Field(default=None, description="Optional project ID for context merging")
