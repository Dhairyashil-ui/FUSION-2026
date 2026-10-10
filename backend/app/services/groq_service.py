import logging
from typing import Optional, Dict, Any
from groq import (
    Groq,
    GroqError,
    AuthenticationError,
    RateLimitError,
    APIConnectionError,
    APIStatusError
)
from app.config import settings

logger = logging.getLogger(__name__)


class GroqServiceException(Exception):
    """Base exception for GroqService errors."""
    pass


class GroqConfigurationError(GroqServiceException):
    """Raised when configuration (API key or model) is missing or invalid."""
    pass


class GroqAuthenticationError(GroqServiceException):
    """Raised when Groq API key is invalid or unauthorized."""
    pass


class GroqRateLimitError(GroqServiceException):
    """Raised when Groq API rate limit is exceeded."""
    pass


class GroqEmptyResponseError(GroqServiceException):
    """Raised when Groq returns an empty or blank response."""
    pass


class GroqAPIError(GroqServiceException):
    """Raised on general API or network failures."""
    pass


class GroqService:
    """
    Reusable Groq LLM service.
    
    Responsible solely for communication with the Groq API.
    Contains no application-specific geospatial or query extraction logic.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        self._client: Optional[Groq] = None

    def _get_client(self) -> Groq:
        """Validates configuration and initializes the Groq client lazily."""
        if not self.api_key:
            raise GroqConfigurationError(
                "GROQ_API_KEY is not configured. Please set GROQ_API_KEY in your .env file."
            )
        if not self.model:
            raise GroqConfigurationError(
                "GROQ_MODEL is not configured. Please set GROQ_MODEL in your .env file."
            )
        if self._client is None:
            self._client = Groq(
                api_key=self.api_key,
                max_retries=0,
                timeout=3.0
            )
        return self._client

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        response_format: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Sends system and user prompts to Groq and returns the generated text response.

        Args:
            system_prompt: The guiding instructions for the model.
            user_prompt: The prompt or input from the user/caller.
            temperature: Sampling temperature (default 0 for deterministic outputs).
            response_format: Optional dict (e.g. {"type": "json_object"} for JSON mode).

        Returns:
            str: Response text returned by the model.

        Raises:
            GroqConfigurationError: When API key or model is missing.
            GroqAuthenticationError: When API key is rejected by Groq.
            GroqRateLimitError: When rate limits are reached.
            GroqEmptyResponseError: When LLM response is empty.
            GroqAPIError: For connectivity or general Groq API errors.
        """
        client = self._get_client()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        logger.info(f"Groq request started (model: {self.model})")

        try:
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            if response_format:
                kwargs["response_format"] = response_format

            chat_completion = client.chat.completions.create(**kwargs)

            if not chat_completion.choices:
                logger.error("Groq request failed: No choices returned in completion")
                raise GroqEmptyResponseError("Groq returned an empty response choices list.")

            first_choice = chat_completion.choices[0]
            content = first_choice.message.content

            if not content or not content.strip():
                logger.error("Groq request failed: Empty content in response message")
                raise GroqEmptyResponseError("Groq returned an empty response message.")

            logger.info("Groq request completed successfully")
            return content.strip()

        except AuthenticationError as e:
            logger.error("Groq request failed: Authentication failure")
            raise GroqAuthenticationError("Invalid or unauthorized Groq API key.") from e

        except RateLimitError as e:
            logger.error("Groq request failed: Rate limit exceeded")
            raise GroqRateLimitError("Groq rate limit exceeded. Please try again later.") from e

        except APIConnectionError as e:
            logger.error("Groq request failed: Connection error")
            raise GroqAPIError("Could not connect to Groq API. Please verify network connectivity.") from e

        except APIStatusError as e:
            if response_format and (e.status_code == 400 or "json_validate_failed" in str(e)):
                logger.warning(
                    f"Groq rejected constrained JSON mode with {e.status_code}. Retrying without response_format constraint..."
                )
                try:
                    kwargs_retry = {
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                    }
                    retry_completion = client.chat.completions.create(**kwargs_retry)
                    if retry_completion.choices:
                        retry_content = retry_completion.choices[0].message.content
                        if retry_content and retry_content.strip():
                            logger.info("Groq retry without response_format succeeded")
                            return retry_content.strip()
                except Exception as retry_err:
                    logger.error(f"Groq retry without response_format failed: {retry_err}")

            logger.error(f"Groq request failed: API status error (status_code={e.status_code})")
            raise GroqAPIError(f"Groq API returned error status {e.status_code}: {e.message}") from e

        except (GroqConfigurationError, GroqEmptyResponseError):
            raise

        except GroqError as e:
            logger.error(f"Groq request failed: Groq SDK error - {e}")
            raise GroqAPIError(f"Groq API error: {str(e)}") from e

        except Exception as e:
            logger.error(f"Groq request failed: Unexpected error - {type(e).__name__}")
            raise GroqAPIError(f"Unexpected error communicating with Groq: {str(e)}") from e


# Singleton service instance for application-wide use
groq_service = GroqService()
