from datetime import datetime
from uuid import UUID
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class WhereSummary(BaseModel):
    """Where component preserved in summary."""
    value: Optional[str] = None
    type: Optional[str] = None


class MeasurementSummary(BaseModel):
    """Measurement component preserved in summary."""
    value: Optional[str] = None


class ConversationSummarySchema(BaseModel):
    """
    Cumulative structured state representation created after every 10 conversation turns.
    Preserves all confirmed dimensions, corrections, constraints, and unresolved questions.
    """
    what: Optional[str] = Field(default=None, description="Analytical problem or phenomenon")
    where: Optional[WhereSummary] = Field(default=None, description="Area of Interest")
    target: List[str] = Field(default_factory=list, description="Target entities/objects")
    measurement: Optional[MeasurementSummary] = Field(default=None, description="Spatial relationships, constraints, filters and operations")
    output_format: List[str] = Field(default_factory=list, description="Requested output artifacts")
    confirmed_information: List[str] = Field(
        default_factory=list,
        description="Factual assertions confirmed by the user across turns"
    )
    important_constraints: List[str] = Field(
        default_factory=list,
        description="Explicit constraints or boundaries specified by the user"
    )
    unresolved_information: List[str] = Field(
        default_factory=list,
        description="Information points still pending user clarification"
    )
    user_corrections: List[str] = Field(
        default_factory=list,
        description="Explicit modifications/overrides made by the user across turns"
    )
    summary_text: Optional[str] = Field(
        default=None,
        description="Concise human-readable synopsis of current conversational state"
    )
    current_state: Dict[str, Any] = Field(
        default_factory=dict,
        description="Normalized 5-field QueryUnderstanding state dictionary"
    )


class ConversationSummaryRead(BaseModel):
    """Pydantic representation of the database record in conversation_summaries."""
    id: UUID
    project_id: UUID
    summary_start_conversation: int
    summary_end_conversation: int
    summary_text: str
    structured_state: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
