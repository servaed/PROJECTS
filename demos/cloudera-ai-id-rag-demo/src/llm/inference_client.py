"""LLM client factory and OpenAI-compatible client.

Supported providers via this module (OpenAI-compatible API):
  - cloudera  : Cloudera AI Inference Service
  - openai    : OpenAI API
  - azure     : Azure OpenAI
  - local     : Ollama, LM Studio, vLLM, or any OpenAI-compatible local server

Non-compatible providers are imported lazily from their own modules:
  - bedrock   : src.llm.bedrock_client.BedrockClient
  - anthropic : src.llm.anthropic_client.AnthropicClient

The public entry point is get_llm_client() — it returns the right client
based on settings.llm_provider.
"""

from collections.abc import Generator

from src.llm.base import BaseLLMClient, LLMResponse
from src.config.settings import settings
from src.config.logging import get_logger

logger = get_logger(__name__)


class InferenceClient(BaseLLMClient):
    """OpenAI-compatible LLM client.

    Handles: cloudera, openai, azure, local providers.
    Uses the standard `openai` Python SDK; Azure uses AzureOpenAI.
    """

    def __init__(self) -> None:
        self._model = settings.llm_model_id
        self._client = self._build_client()

    def _build_client(self):
        if settings.llm_provider == "azure":
            from openai import AzureOpenAI
            logger.info(
                "LLM provider: Azure OpenAI — endpoint=%s, deployment=%s",
                settings.azure_openai_endpoint,
                settings.azure_openai_deployment,
            )
            return AzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
            )

        from openai import OpenAI
        logger.info(
            "LLM provider: %s — url=%s, model=%s",
            settings.llm_provider,
            settings.llm_base_url,
            self._model,
        )
        return OpenAI(
            base_url=settings.llm_base_url or None,
            api_key=settings.llm_api_key or "no-key",
        )

    def chat(
        self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 1024
    ) -> LLMResponse:
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

    def stream_chat(
        self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 1024
    ) -> Generator[str, None, None]:
        logger.debug("LLM stream: model=%s, messages=%d", self._model, len(messages))
        stream = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def is_available(self) -> bool:
        if not settings.llm_base_url and settings.llm_provider not in ("openai",):
            return False
        try:
            self._client.models.list()
            return True
        except Exception:
            return False


# ── Factory ────────────────────────────────────────────────────────────────


def get_llm_client() -> BaseLLMClient:
    """Return the configured LLM client based on LLM_PROVIDER.

    Provider dispatch:
      cloudera / openai / azure / local → InferenceClient (OpenAI-compatible)
      bedrock                           → BedrockClient (boto3 Converse API)
      anthropic                         → AnthropicClient (anthropic SDK)
    """
    provider = settings.llm_provider

    if provider == "bedrock":
        from src.llm.bedrock_client import BedrockClient
        return BedrockClient()

    if provider == "anthropic":
        from src.llm.anthropic_client import AnthropicClient
        return AnthropicClient()

    # cloudera, openai, azure, local — all handled by InferenceClient
    return InferenceClient()
