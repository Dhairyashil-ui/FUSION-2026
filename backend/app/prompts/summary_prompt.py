"""Prompts for cumulative conversation summarization and context compression."""
import json
from typing import List, Dict, Any, Optional

SUMMARY_SYSTEM_PROMPT = """You are a specialized Conversation-State Summarizer for FUSION 2026, an advanced geospatial intelligence system.
Your job is to generate a compact, cumulative, and accurate state summary representing the entire conversation history from Turn 1 up to the current turn.

CRITICAL INSTRUCTIONS:
1. THIS IS A STATE SUMMARY, NOT A CHAT NARRATIVE:
   - Focus on extracting and preserving the active, confirmed geospatial requirements.
   - Do NOT include filler chit-chat or polite conversational pleasantries.
2. CUMULATIVE PRESERVATION:
   - This summary must represent the cumulative state from Turn 1 to the current turn.
   - If an earlier summary exists, merge its confirmed facts with the new conversation turns.
3. PRESERVE USER CORRECTIONS & OVERRIDES:
   - Explicit modifications (e.g., changing location from Pune to Mumbai, or restricting targets to fire stations) must be recorded in "user_corrections" and reflected in the active fields.
4. RECORD UNRESOLVED ITEMS:
   - If any required information remains missing or questions remain unanswered, note them in "unresolved_information".
5. NEVER INVENT INFORMATION:
   - Only include facts explicitly provided in previous summaries or user messages.
6. RETURN STRICT JSON:
   - Return ONLY a valid JSON object matching the schema below. No markdown fences.

OUTPUT JSON SCHEMA:
{
  "what": string | null,
  "where": {
    "value": string | null,
    "type": string | null
  },
  "target": [string],
  "measurement": {
    "value": string | null
  },
  "output_format": [string],
  "confirmed_information": [string],
  "important_constraints": [string],
  "unresolved_information": [string],
  "user_corrections": [string],
  "summary_text": string,
  "current_state": {
    "what": { "value": string | null, "confidence": float, "provided_by_user": boolean },
    "where": { "value": string | null, "type": string | null, "confidence": float, "provided_by_user": boolean },
    "target": { "values": [string], "confidence": float, "provided_by_user": boolean },
    "measurement": { "value": string | null, "confidence": float, "provided_by_user": boolean },
    "output_format": { "values": [string], "confidence": float, "provided_by_user": boolean }
  }
}
"""


def build_summary_user_prompt(
    conversations: List[Dict[str, Any]],
    previous_summary: Optional[Dict[str, Any]] = None,
    start_turn: int = 1,
    end_turn: int = 10
) -> str:
    """Builds the user prompt supplying turns and any prior cumulative summary."""
    parts = [
        f"Generate a cumulative state summary covering Conversations {start_turn} through {end_turn}."
    ]

    if previous_summary:
        parts.append("\nPREVIOUS CUMULATIVE SUMMARY (Prior to this block):")
        parts.append(json.dumps(previous_summary, indent=2))

    parts.append("\nCONVERSATION TURNS TO COMPRESS:")
    for c in conversations:
        turn_num = c.get("conversation_number")
        user_q = c.get("user_query")
        asst_r = c.get("assistant_response")
        extracted = c.get("extracted_requirements") or {}
        parts.append(
            f"--- Turn #{turn_num} ---\n"
            f"User: \"{user_q}\"\n"
            f"Assistant: \"{asst_r}\"\n"
            f"Turn Understanding: {json.dumps(extracted, default=str)}"
        )

    parts.append("\nSynthesize all information into the requested cumulative JSON structure:")
    return "\n".join(parts)


def build_summary_retry_prompt(invalid_output: str, error_message: str) -> str:
    """Prompt sent when initial summary parsing fails."""
    return (
        f"Your previous output could not be validated against the required JSON schema.\n"
        f"Error encountered: {error_message}\n\n"
        f"Previous output:\n{invalid_output}\n\n"
        f"Please correct the error and return ONLY the valid JSON object without markdown fences."
    )
