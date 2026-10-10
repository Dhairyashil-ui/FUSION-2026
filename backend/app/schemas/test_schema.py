from typing import Optional
from pydantic import BaseModel, Field
from app.prompts.test_prompt import TEST_USER_PROMPT


class GroqTestRequest(BaseModel):
    """Request payload for Groq test endpoint."""
    query: Optional[str] = Field(
        default=TEST_USER_PROMPT,
        description="Test prompt to send to Groq"
    )


class GroqTestResponse(BaseModel):
    """Response payload for Groq test endpoint."""
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None
