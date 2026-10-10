from uuid import UUID
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.query_schema import QueryUnderstanding
from app.schemas.sufficiency_schema import SufficiencyResult
from app.schemas.planner_schema import QueryPlan


class QueryConversationRequest(BaseModel):
    """Incoming request for multi-turn query handling."""
    project_id: UUID = Field(..., description="UUID of the existing FUSION project")
    query: str = Field(..., min_length=1, description="User query or clarification")
    previous_understanding: Optional[QueryUnderstanding] = Field(
        default=None,
        description="Optional client-side prior understanding state for fail-safe continuity"
    )


class ConversationTurnResponse(BaseModel):
    """Response returned for a conversation turn."""
    conversation_number: int = Field(..., description="Sequential conversation number inside this project")
    user_query: str = Field(..., description="The query submitted by the user")
    understanding: QueryUnderstanding = Field(..., description="Updated 5-field query understanding")
    sufficiency: SufficiencyResult = Field(..., description="Sufficiency evaluation of the updated understanding")
    assistant_response: str = Field(..., description="Targeted response or clarification question for the user")
    is_conversational: bool = Field(default=False, description="True if query was conversational chit-chat or off-topic")
    plan: Optional[QueryPlan] = Field(default=None, description="Structured AI execution plan generated when query is READY")
    deliverable: Optional[Dict[str, Any]] = Field(default=None, description="Part 3 Final Spatial Output Deliverable")
