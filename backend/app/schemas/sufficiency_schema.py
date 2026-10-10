"""Pydantic schemas for query sufficiency checking."""
from typing import List, Dict, Literal
from pydantic import BaseModel, Field
from app.schemas.query_schema import QueryUnderstanding


SufficiencyStatus = Literal["READY", "NEEDS_INFORMATION"]


class KnownInformation(BaseModel):
    """Tracks which of the 5 query dimensions are provided and clear."""
    what: bool = Field(default=False)
    where: bool = Field(default=False)
    target: bool = Field(default=False)
    measurement: bool = Field(default=False)
    output_format: bool = Field(default=False)


class SufficiencyResult(BaseModel):
    """Evaluation result detailing whether sufficient information exists to proceed."""
    status: SufficiencyStatus = Field(
        ...,
        description="READY if sufficient to proceed with geospatial analysis; NEEDS_INFORMATION if clarifications required."
    )
    is_sufficient: bool = Field(
        ...,
        description="True if READY, False if NEEDS_INFORMATION"
    )
    known_information: KnownInformation = Field(
        ...,
        description="Boolean flags indicating which components were identified."
    )
    missing_information: List[str] = Field(
        default_factory=list,
        description="List of component keys that are required but missing (e.g. ['where', 'measurement'])."
    )
    questions_for_user: List[str] = Field(
        default_factory=list,
        description="Concise, targeted follow-up questions for missing required information only."
    )
    reason: str = Field(
        ...,
        description="Factual summary explaining what is known and what is missing."
    )


class QueryCheckResponse(BaseModel):
    """Complete response returned by POST /api/query/check."""
    understanding: QueryUnderstanding
    sufficiency: SufficiencyResult
