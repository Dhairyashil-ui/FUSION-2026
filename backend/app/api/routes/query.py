import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.conversation import Conversation
from app.models.extracted_requirement import ExtractedRequirement
from app.schemas.query_schema import QueryParseRequest, QueryUnderstanding
from app.schemas.sufficiency_schema import QueryCheckResponse
from app.schemas.conversation_schema import QueryConversationRequest, ConversationTurnResponse
from app.services.query_parser import query_parser, QueryParserException
from app.services.context_merger import context_merger
from app.services.sufficiency_checker import sufficiency_checker
from app.services.conversation_manager import conversation_manager, ProjectNotFoundError
from app.services.groq_service import GroqServiceException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["Query Understanding"])


@router.post(
    "",
    response_model=ConversationTurnResponse,
    status_code=status.HTTP_200_OK,
    summary="Process a conversation turn with context merging and database tracking"
)
async def process_conversation_query(
    payload: QueryConversationRequest,
    db: Session = Depends(get_db)
) -> ConversationTurnResponse:
    """
    Core conversational query endpoint.
    Loads previous conversation state for the given project, merges context with the new query,
    evaluates sufficiency ON THE MERGED STATE, persists the turn to the database, and returns the updated state.
    """
    try:
        result = conversation_manager.process_query(
            project_id=payload.project_id,
            user_query=payload.query,
            db=db,
            client_previous_context=payload.previous_understanding
        )
        return result

    except ProjectNotFoundError as proj_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(proj_err)
        )

    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )

    except QueryParserException as parse_err:
        logger.error(f"Query parsing error in conversation turn: {parse_err}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(parse_err)
        )

    except GroqServiceException as groq_err:
        logger.error(f"Groq service error in conversation turn: {groq_err}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM extraction service error: {str(groq_err)}"
        )

    except Exception as exc:
        logger.error(f"Unexpected error in /api/query: {type(exc).__name__} - {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal error occurred while processing the conversation query."
        )


@router.post(
    "/parse",
    response_model=QueryUnderstanding,
    status_code=status.HTTP_200_OK,
    summary="Parse natural language query into 5 geospatial dimensions"
)
async def parse_query(
    payload: QueryParseRequest,
    db: Session = Depends(get_db)
) -> QueryUnderstanding:
    """
    Parses a user's natural language geospatial query and extracts the 5 core components.
    If project_id is provided, incorporates previous session context via ContextMerger.
    """
    try:
        previous_context: Optional[QueryUnderstanding] = None
        if payload.project_id:
            last_conv = (
                db.query(Conversation)
                .filter(Conversation.project_id == payload.project_id)
                .order_by(Conversation.conversation_number.desc())
                .first()
            )
            if last_conv:
                last_req = (
                    db.query(ExtractedRequirement)
                    .filter(ExtractedRequirement.conversation_id == last_conv.id)
                    .first()
                )
                if last_req:
                    prev_dict = {
                        "what": last_req.what or {},
                        "where": last_req.where_data or {},
                        "target": last_req.target or {},
                        "measurement": last_req.measurement_data or {},
                        "output_format": last_req.output_format or {},
                    }
                    try:
                        previous_context = QueryUnderstanding.model_validate(prev_dict)
                    except Exception:
                        previous_context = None

        extracted = query_parser.parse(payload.query)
        if previous_context:
            return context_merger.merge(previous_context, extracted, payload.query)
        return extracted

    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )

    except QueryParserException as parse_err:
        logger.error(f"Query parsing error: {parse_err}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(parse_err)
        )

    except GroqServiceException as groq_err:
        logger.error(f"Groq service error during parsing: {groq_err}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM extraction service error: {str(groq_err)}"
        )

    except Exception as exc:
        logger.error(f"Unexpected error in /api/query/parse: {type(exc).__name__} - {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal error occurred while parsing the query."
        )


@router.post(
    "/check",
    response_model=QueryCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Parse query and evaluate analytical sufficiency"
)
async def check_query(
    payload: QueryParseRequest,
    db: Session = Depends(get_db)
) -> QueryCheckResponse:
    """
    Parses query into 5 dimensions, merges with existing session context if project_id is provided,
    then evaluates analytical sufficiency strictly on the MERGED state.
    """
    try:
        previous_context: Optional[QueryUnderstanding] = None
        if payload.project_id:
            last_conv = (
                db.query(Conversation)
                .filter(Conversation.project_id == payload.project_id)
                .order_by(Conversation.conversation_number.desc())
                .first()
            )
            if last_conv:
                last_req = (
                    db.query(ExtractedRequirement)
                    .filter(ExtractedRequirement.conversation_id == last_conv.id)
                    .first()
                )
                if last_req:
                    prev_dict = {
                        "what": last_req.what or {},
                        "where": last_req.where_data or {},
                        "target": last_req.target or {},
                        "measurement": last_req.measurement_data or {},
                        "output_format": last_req.output_format or {},
                    }
                    try:
                        previous_context = QueryUnderstanding.model_validate(prev_dict)
                    except Exception:
                        previous_context = None

        extracted = query_parser.parse(payload.query)
        if previous_context:
            merged = context_merger.merge(previous_context, extracted, payload.query)
        else:
            merged = extracted

        sufficiency = sufficiency_checker.check(merged)
        return QueryCheckResponse(
            understanding=merged,
            sufficiency=sufficiency
        )

    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )

    except QueryParserException as parse_err:
        logger.error(f"Query parsing error: {parse_err}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(parse_err)
        )

    except GroqServiceException as groq_err:
        logger.error(f"Groq service error during check: {groq_err}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM extraction service error: {str(groq_err)}"
        )

    except Exception as exc:
        logger.error(f"Unexpected error in /api/query/check: {type(exc).__name__} - {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal error occurred while checking query sufficiency."
        )
