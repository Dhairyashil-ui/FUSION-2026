import logging
from fastapi import APIRouter
from app.services.groq_service import (
    GroqService,
    GroqServiceException,
    GroqConfigurationError,
    GroqAuthenticationError,
    GroqRateLimitError,
    GroqEmptyResponseError,
    GroqAPIError,
)
from app.prompts.test_prompt import TEST_SYSTEM_PROMPT, TEST_USER_PROMPT
from app.schemas.test_schema import GroqTestRequest, GroqTestResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/test", tags=["Test"])


@router.post("/groq", response_model=GroqTestResponse)
async def run_groq_test_endpoint(payload: GroqTestRequest) -> GroqTestResponse:
    """
    Sends a test prompt to Groq to verify API connectivity and authentication.
    Does not perform any geospatial extraction or business logic.
    """
    user_prompt = payload.query.strip() if payload.query and payload.query.strip() else TEST_USER_PROMPT
    
    try:
        service = GroqService()
        llm_response = service.generate(
            system_prompt=TEST_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.0
        )
        return GroqTestResponse(
            success=True,
            response=llm_response
        )

    except (
        GroqConfigurationError,
        GroqAuthenticationError,
        GroqRateLimitError,
        GroqEmptyResponseError,
        GroqAPIError,
        GroqServiceException
    ) as exc:
        logger.warning(f"Groq test endpoint handled error: {exc}")
        return GroqTestResponse(
            success=False,
            error=str(exc)
        )

    except Exception as exc:
        logger.error(f"Groq test endpoint unexpected error: {type(exc).__name__}")
        return GroqTestResponse(
            success=False,
            error="An unexpected internal error occurred while connecting to Groq."
        )
