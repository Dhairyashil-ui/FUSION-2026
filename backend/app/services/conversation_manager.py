"""FUSION 2026 - Conversational Query & Context Lifecycle Manager.

Coordinates multi-turn geospatial conversation state following the strict lifecycle:
User message -> Extract -> Merge with previous state -> Validate merged state -> Sufficiency check -> Query Planner (when READY) -> Response

Maintains strict separation of responsibilities:
- QueryParser: Single-turn extraction of the 5 dimensions.
- ContextMerger: Deterministic, domain-agnostic state accumulation and preservation.
- SufficiencyChecker: Evaluates completeness on the merged state and identifies missing fields.
- QueryPlanner: Generates structured AI execution plans when all 5 dimensions are READY.
- SummaryService: Long-horizon 10-turn cumulative summarization.
"""

import logging
from uuid import UUID
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.conversation import Conversation
from app.models.extracted_requirement import ExtractedRequirement
from app.schemas.query_schema import QueryUnderstanding
from app.schemas.conversation_schema import ConversationTurnResponse
from app.schemas.planner_schema import QueryPlan
from app.services.query_parser import QueryParser, query_parser
from app.services.context_merger import ContextMerger, context_merger
from app.services.sufficiency_checker import SufficiencyChecker, sufficiency_checker
from app.services.query_planner import QueryPlanner, query_planner
from app.services.summary_service import SummaryService, summary_service, SummaryServiceException
from app.services.retrieval_engine import RetrievalEngine, retrieval_engine

logger = logging.getLogger(__name__)


class ProjectNotFoundError(Exception):
    """Raised when a specified project does not exist."""
    pass


class ConversationManager:
    """
    Coordinates multi-turn conversation state, query interpretation,
    sufficiency evaluation, AI plan generation, data retrieval execution, 10-turn cumulative summarization, and database persistence.
    """

    def __init__(
        self,
        parser: Optional[QueryParser] = None,
        merger: Optional[ContextMerger] = None,
        checker: Optional[SufficiencyChecker] = None,
        planner: Optional[QueryPlanner] = None,
        summarizer: Optional[SummaryService] = None,
        retriever: Optional[RetrievalEngine] = None
    ):
        self.query_parser = parser or query_parser
        self.context_merger = merger or context_merger
        self.sufficiency_checker = checker or sufficiency_checker
        self.query_planner = planner or query_planner
        self.summary_service = summarizer or summary_service
    def process_query(
        self,
        project_id: UUID,
        user_query: str,
        db: Session,
        client_previous_context: Optional[QueryUnderstanding] = None
    ) -> ConversationTurnResponse:
        """
        Processes a query turn within an existing project session.

        Lifecycle:
        1. Validate project existence and determine turn number.
        2. Retrieve prior cumulative state from last turn or summary.
        3. Extract 5 dimensions from the current user message (QueryParser).
        4. Merge current extraction with complete previous state (ContextMerger).
        5. Validate merged state.
        6. Run SufficiencyChecker on the merged state.
        7. If READY: Generate validated QueryPlan (QueryPlanner). If NEEDS_INFORMATION: prompt for missing fields.
        8. Persist conversation and updated requirements to database.
        9. Check 10-turn summarization milestone.
        """
        if not user_query or not user_query.strip():
            raise ValueError("Query string cannot be empty.")

        query_str = user_query.strip()

        # 1. Validate project existence
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            logger.warning(f"Project not found: {project_id}")
            raise ProjectNotFoundError(f"Project with ID '{project_id}' does not exist.")

        # 2. Determine conversation number
        last_conversation = (
            db.query(Conversation)
            .filter(Conversation.project_id == project_id)
            .order_by(Conversation.conversation_number.desc())
            .first()
        )

        next_conversation_number = (last_conversation.conversation_number + 1) if last_conversation else 1

        # 3. Retrieve prior cumulative state
        previous_context: Optional[QueryUnderstanding] = None
        if last_conversation:
            last_requirement = (
                db.query(ExtractedRequirement)
                .filter(ExtractedRequirement.conversation_id == last_conversation.id)
                .first()
            )
            if last_requirement:
                prev_dict = {
                    "what": last_requirement.what or {},
                    "where": last_requirement.where_data or {},
                    "target": last_requirement.target or {},
                    "measurement": last_requirement.measurement_data or {},
                    "output_format": last_requirement.output_format or {},
                }
                try:
                    previous_context = QueryUnderstanding.model_validate(prev_dict)
                except Exception as exc:
                    logger.error(f"Failed to deserialize previous context from last_requirement: {exc}")
                    previous_context = None

        # If client provided prior context, reconcile with DB to prevent state loss
        if client_previous_context is not None:
            if previous_context is None:
                previous_context = client_previous_context
            else:
                previous_context = self.context_merger.merge(
                    previous=previous_context,
                    current=client_previous_context,
                    user_message=""
                )

        # Check for cumulative summary in long sessions (turn > 10)
        latest_summary = self.summary_service.get_latest_summary(project_id, db)

        # 4. STEP 1 & 2: Extract & Merge
        if next_conversation_number > 10 and latest_summary:
            summary_end = latest_summary.summary_end_conversation
            unsummarized_convs = (
                db.query(Conversation)
                .filter(
                    Conversation.project_id == project_id,
                    Conversation.conversation_number > summary_end,
                    Conversation.conversation_number < next_conversation_number
                )
                .order_by(Conversation.conversation_number.asc())
                .all()
            )
            unsummarized_turns: List[Dict[str, Any]] = [
                {
                    "conversation_number": c.conversation_number,
                    "user_query": c.user_query
                }
                for c in unsummarized_convs
            ]
            extracted_turn = self.query_parser.parse(
                query=query_str,
                previous_summary=latest_summary.structured_state,
                unsummarized_turns=unsummarized_turns
            )
            merged_understanding = self.context_merger.merge(
                previous=previous_context,
                current=extracted_turn,
                user_message=query_str
            )
        else:
            extracted_turn = self.query_parser.parse(query=query_str)
            merged_understanding = self.context_merger.merge(
                previous=previous_context,
                current=extracted_turn,
                user_message=query_str
            )

        # 5. STEP 3: Validate merged state
        validated_understanding = QueryUnderstanding.model_validate(merged_understanding.model_dump())

        # 6. STEP 4: Sufficiency check on the MERGED state
        sufficiency_result = self.sufficiency_checker.check(validated_understanding)

        # 7. STEP 5: Formulate response and generate AI Query Plan if READY
        q_clean = query_str.lower().strip("!?,. ")
        GREETINGS = {"hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening", "howdy", "sup", "yo"}
        HOW_ARE_YOU = {"how are you", "how are you doing", "what's up", "how's it going", "how are you today"}
        ACKNOWLEDGEMENTS = {"thanks", "thank you", "thx", "appreciate it", "many thanks", "ok", "okay", "cool", "great", "nice", "awesome", "perfect", "got it", "understood", "sure", "alright", "fine"}
        FAREWELLS = {"bye", "goodbye", "see you", "cya", "farewell"}
        BOT_INQUIRY = {"who are you", "what are you", "what is your name", "what can you do", "help", "help me"}

        is_conversational = False
        simple_conversational_response = None
        generated_plan: Optional[QueryPlan] = None

        if q_clean in GREETINGS:
            is_conversational = True
            simple_conversational_response = "Hello! How can I help you today?"
        elif q_clean in HOW_ARE_YOU:
            is_conversational = True
            simple_conversational_response = "I'm doing well, thank you! How can I help you today?"
        elif q_clean in ACKNOWLEDGEMENTS:
            is_conversational = True
            simple_conversational_response = "You're welcome! Let me know if you need anything else."
        elif q_clean in FAREWELLS:
            is_conversational = True
            simple_conversational_response = "Goodbye! Have a great day!"
        elif q_clean in BOT_INQUIRY:
            is_conversational = True
            simple_conversational_response = "I am FUSION 2026, an intelligent GeoAI assistant. I can help analyze satellite imagery, track spatial changes, predict risks, and map areas of interest."
        else:
            has_no_geo_info = (
                not extracted_turn.what.provided_by_user
                and not extracted_turn.where.provided_by_user
                and not extracted_turn.measurement.provided_by_user
                and len(extracted_turn.target.values) == 0
                and len(extracted_turn.output_format.values) == 0
            )
            is_execution_cmd = any(word in q_clean for word in ["run", "execute", "start", "proceed", "yes", "confirm", "generate"])
            if has_no_geo_info and not is_execution_cmd and len(q_clean.split()) < 20:
                try:
                    simple_conversational_response = self.query_parser.service.generate(
                        system_prompt="You are a helpful assistant. The user sent a general or off-topic message not related to geospatial analysis. Answer it simply, politely, and briefly in 1 to 2 sentences without mentioning datasets or technical JSON.",
                        user_prompt=query_str,
                        temperature=0.3
                    )
                    if simple_conversational_response and simple_conversational_response.strip():
                        is_conversational = True
                except Exception as e:
                    logger.warning(f"Could not generate off-topic response: {e}")

        deliverable_payload: Optional[Dict[str, Any]] = None
        if is_conversational and simple_conversational_response:
            assistant_response = simple_conversational_response
        elif sufficiency_result.status == "READY":
            # Generate structured AI Query Plan for user confirmation
            generated_plan = self.query_planner.generate_plan(validated_understanding)
            where_name = validated_understanding.where.value or 'specified area'
            assistant_response = f"All 6 query dimensions satisfied. Machine-readable AI Execution Plan generated for {where_name}. Review the plan and click 'Proceed with this Plan' to run the execution pipeline."
            deliverable_payload = None

        else:
            # Missing fields -> prompt user for missing fields. Do NOT show plan output until complete.
            if sufficiency_result.questions_for_user:
                assistant_response = " ".join(sufficiency_result.questions_for_user)
            else:
                assistant_response = "Additional information is required to proceed."

        # 8. STEP 6: Store conversation record
        conversation = Conversation(
            project_id=project_id,
            conversation_number=next_conversation_number,
            user_query=query_str,
            assistant_response=assistant_response
        )
        try:
            db.add(conversation)
            db.flush()

            requirement = ExtractedRequirement(
                conversation_id=conversation.id,
                what=validated_understanding.what.model_dump(),
                where_data=validated_understanding.where.model_dump(),
                target=validated_understanding.target.model_dump(),
                measurement_data=validated_understanding.measurement.model_dump(),
                output_format=validated_understanding.output_format.model_dump(),
                missing_information=sufficiency_result.missing_information,
                questions_for_user=sufficiency_result.questions_for_user,
                is_sufficient=sufficiency_result.is_sufficient
            )
            db.add(requirement)
            db.commit()
        except Exception as db_err:
            db.rollback()
            logger.warning(f"ConversationManager: DB persistence notice: {db_err}. Proceeding with memory response.")

        # 10. STEP 8: Check 10-turn summarization boundary (turns 10, 20, 30...)
        if next_conversation_number % 10 == 0:
            try:
                self.summary_service.create_summary(
                    project_id=project_id,
                    start_conversation=1,
                    end_conversation=next_conversation_number,
                    db=db
                )
                logger.info(
                    f"Successfully generated cumulative SUMMARY_1_{next_conversation_number} for project {project_id}"
                )
            except Exception as summ_err:
                logger.warning(
                    f"Summary generation at turn #{next_conversation_number} encountered warning: {summ_err}. Conversation record was preserved."
                )

        return ConversationTurnResponse(
            conversation_number=next_conversation_number,
            user_query=query_str,
            understanding=validated_understanding,
            sufficiency=sufficiency_result,
            assistant_response=assistant_response,
            is_conversational=is_conversational,
            plan=generated_plan,
            deliverable=deliverable_payload
        )


# Singleton instance
conversation_manager = ConversationManager()
