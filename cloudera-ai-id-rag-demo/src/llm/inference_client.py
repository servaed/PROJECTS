"""Cloudera AI Inference client — OpenAI-compatible API.

Works with Cloudera AI Inference Service endpoints as well as any
OpenAI-compatible local or cloud endpoint (LM Studio, vLLM, etc.).
"""

from openai import OpenAI
from src.llm.base import BaseLLMClient, LLMResponse
from src.config.settings import settings
from src.config.logging import get_logger

logger = get_logger(__name__)


class InferenceClient(BaseLLMClient):
    """OpenAI-compatible LLM client for Cloudera AI Inference and compatible APIs."""

    def __init__(self) -> None:
        self._model = settings.llm_model_id
        self._client = OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or "no-key",
        )

    def chat(self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 1024) -> LLMResponse:
        logger.debug("LLM request: model=%s, messages=%d", self._model, len(messages))
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = response.choices[0]
        usage = response.usage
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

    def is_available(self) -> bool:
        if not settings.llm_base_url:
            return False
        try:
            self._client.models.list()
            return True
        except Exception:
            return False


def get_llm_client() -> BaseLLMClient:
    """Factory — returns the configured LLM client."""
    return InferenceClient()
