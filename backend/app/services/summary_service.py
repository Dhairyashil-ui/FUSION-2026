import json
import re
import logging
from uuid import UUID
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.models.conversation import Conversation
from app.models.extracted_requirement import ExtractedRequirement
from app.models.conversation_summary import ConversationSummary
from app.schemas.summary_schema import ConversationSummarySchema
from app.services.groq_service import GroqService, groq_service, GroqServiceException
from app.prompts.summary_prompt import (
    SUMMARY_SYSTEM_PROMPT,
    build_summary_user_prompt,
    build_summary_retry_prompt,
)

logger = logging.getLogger(__name__)


class SummaryServiceException(Exception):
    """Raised when conversation summarization fails or cannot be validated."""
    pass


class SummaryService:
    """
    Manages 10-turn cumulative conversation summarization and context compression.
    Generates compact structured states (SUMMARY_1_10, SUMMARY_1_20, etc.) preserving
    all confirmed geospatial dimensions and corrections.
    """

    def __init__(self, service: Optional[GroqService] = None):
        self.groq_service = service or groq_service

    def get_latest_summary(self, project_id: UUID, db: Session) -> Optional[ConversationSummary]:
        """
        Retrieves the latest cumulative summary for a project (highest summary_end_conversation).
        """
        return (
            db.query(ConversationSummary)
            .filter(ConversationSummary.project_id == project_id)
            .order_by(ConversationSummary.summary_end_conversation.desc())
            .first()
        )

    def _clean_json(self, text: str) -> str:
        """Strips markdown fences and extra whitespace."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()

    def _call_and_validate(self, system_prompt: str, user_prompt: str) -> ConversationSummarySchema:
        """
        Invokes Groq with the summary prompt and validates against ConversationSummarySchema.
        Retries once with a correction prompt if validation fails.
        """
        raw = self.groq_service.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        cleaned = self._clean_json(raw)

        try:
            data = json.loads(cleaned)
            return ConversationSummarySchema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as err:
            logger.warning(f"Summary initial parse error: {err}. Retrying with correction prompt...")
            retry_prompt = build_summary_retry_prompt(cleaned, str(err))
            raw_retry = self.groq_service.generate(
                system_prompt=system_prompt,
                user_prompt=retry_prompt,
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            cleaned_retry = self._clean_json(raw_retry)
            try:
                data_retry = json.loads(cleaned_retry)
                return ConversationSummarySchema.model_validate(data_retry)
            except Exception as final_err:
                logger.error(f"Summary validation failed after retry: {final_err}")
                raise SummaryServiceException(
                    f"Summary output could not be validated against schema: {final_err}"
                ) from final_err

    def create_summary(
        self,
        project_id: UUID,
        start_conversation: int,
        end_conversation: int,
        db: Session
    ) -> ConversationSummary:
        """
        Creates a cumulative summary covering turns 1 through end_conversation.
        Integrates any previous cumulative summary with new turns.

        Args:
            project_id: Project UUID.
            start_conversation: Always 1 for cumulative summaries.
            end_conversation: Milestone turn number (e.g. 10, 20, 30...).
            db: Database session.

        Returns:
            ConversationSummary: Persisted database record.
        """
        logger.info(f"Generating cumulative SUMMARY_{start_conversation}_{end_conversation} for project {project_id}")

        # 1. Retrieve any prior cumulative summary
        previous_summary = self.get_latest_summary(project_id, db)
        prev_summary_dict: Optional[Dict[str, Any]] = None
        unsummarized_start = start_conversation

        if previous_summary and previous_summary.summary_end_conversation < end_conversation:
            prev_summary_dict = previous_summary.structured_state
            unsummarized_start = previous_summary.summary_end_conversation + 1
            logger.info(
                f"Incorporating prior SUMMARY_1_{previous_summary.summary_end_conversation} into new SUMMARY_1_{end_conversation}"
            )

        # 2. Retrieve unsummarized conversations up to end_conversation
        convs = (
            db.query(Conversation)
            .filter(
                Conversation.project_id == project_id,
                Conversation.conversation_number >= unsummarized_start,
                Conversation.conversation_number <= end_conversation
            )
            .order_by(Conversation.conversation_number.asc())
            .all()
        )

        conversations_data: List[Dict[str, Any]] = []
        for c in convs:
            req = (
                db.query(ExtractedRequirement)
                .filter(ExtractedRequirement.conversation_id == c.id)
                .first()
            )
            extracted_dict: Dict[str, Any] = {}
            if req:
                extracted_dict = {
                    "what": req.what or {},
                    "where": req.where_data or {},
                    "target": req.target or {},
                    "measurement": req.measurement_data or {},
                    "output_format": req.output_format or {},
                }
            conversations_data.append({
                "conversation_number": c.conversation_number,
                "user_query": c.user_query,
                "assistant_response": c.assistant_response,
                "extracted_requirements": extracted_dict
            })

        # 3. Build user prompt and query Groq
        user_prompt = build_summary_user_prompt(
            conversations=conversations_data,
            previous_summary=prev_summary_dict,
            start_turn=start_conversation,
            end_turn=end_conversation
        )

        validated_summary = self._call_and_validate(SUMMARY_SYSTEM_PROMPT, user_prompt)

        # Ensure summary_text is readable
        summary_text = validated_summary.summary_text
        if not summary_text or not summary_text.strip():
            where_name = validated_summary.where.value if validated_summary.where else "unspecified location"
            summary_text = f"Cumulative geospatial summary through Turn {end_conversation}: {validated_summary.what} in {where_name}."

        # 4. Upsert/Record into conversation_summaries
        existing_summary = (
            db.query(ConversationSummary)
            .filter(
                ConversationSummary.project_id == project_id,
                ConversationSummary.summary_start_conversation == start_conversation,
                ConversationSummary.summary_end_conversation == end_conversation
            )
            .first()
        )

        if existing_summary:
            existing_summary.summary_text = summary_text
            existing_summary.structured_state = validated_summary.model_dump()
            db.commit()
            db.refresh(existing_summary)
            summary_record = existing_summary
        else:
            summary_record = ConversationSummary(
                project_id=project_id,
                summary_start_conversation=start_conversation,
                summary_end_conversation=end_conversation,
                summary_text=summary_text,
                structured_state=validated_summary.model_dump()
            )
            db.add(summary_record)
            db.commit()
            db.refresh(summary_record)

        logger.info(
            f"Successfully stored SUMMARY_{start_conversation}_{end_conversation} (id: {summary_record.id})"
        )
        return summary_record


# Singleton instance
summary_service = SummaryService()
