"""Anthropic API client — direct access to Claude models.

Uses the official `anthropic` Python SDK.
Best choice when you want Claude with the most up-to-date features
(extended thinking, tool use, prompt caching) without going through Bedrock.

Install: pip install anthropic
"""

from __future__ import annotations

from collections.abc import Generator

import anthropic

from src.llm.base import BaseLLMClient, LLMResponse
from src.config.settings import settings
from src.config.logging import get_logger

logger = get_logger(__name__)


class AnthropicClient(BaseLLMClient):
    """Anthropic API client for Claude models."""

    def __init__(self) -> None:
        self._model = settings.anthropic_model_id
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        logger.info("LLM provider: Anthropic — model=%s", self._model)

    # ── Internal helpers ───────────────────────────────────────────────────

    @staticmethod
    def _split_messages(messages: list[dict]) -> tuple[str, list[dict]]:
        """Split OpenAI-format messages into (system_text, user_messages).

        The Anthropic Messages API accepts the system prompt as a separate
        top-level parameter, not as a message with role="system".
        """
        system_parts: list[str] = []
        user_messages: list[dict] = []

        for m in messages:
            if m["role"] == "system":
                system_parts.append(m.get("content") or "")
            else:
                user_messages.append({"role": m["role"], "content": m.get("content") or ""})

        return "\n\n".join(system_parts), user_messages

    def _build_kwargs(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> dict:
        system_text, user_messages = self._split_messages(messages)
        kwargs: dict = {
            "model": self._model,
            "messages": user_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_text:
            # Prompt caching: mark the system block as cacheable (5-min TTL).
            # Cache hits cut cost ~90% and first-token latency ~30% for repeated calls.
            kwargs["system"] = [
                {
                    "type": "text",
                    "text": system_text,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        return kwargs

    # ── BaseLLMClient interface ────────────────────────────────────────────

    def chat(
        self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 1024
    ) -> LLMResponse:
        logger.debug("Anthropic request: model=%s, messages=%d", self._model, len(messages))
        kwargs = self._build_kwargs(messages, temperature, max_tokens)
        response = self._client.messages.create(**kwargs)
        usage = response.usage
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_written = getattr(usage, "cache_creation_input_tokens", 0) or 0
        if cache_read or cache_written:
            logger.debug(
                "Anthropic cache: read=%d written=%d (saved ~%.0f%% of input cost)",
                cache_read, cache_written,
                100 * cache_read / max(usage.input_tokens + cache_read, 1),
            )
        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )

    def stream_chat(
        self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 1024
    ) -> Generator[str, None, None]:
        logger.debug("Anthropic stream: model=%s, messages=%d", self._model, len(messages))
        kwargs = self._build_kwargs(messages, temperature, max_tokens)
        with self._client.messages.stream(**kwargs) as stream:
            yield from stream.text_stream
            # Log cache stats after stream completes (usage available via get_final_usage)
            try:
                usage = stream.get_final_usage()
                cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
                if cache_read:
                    logger.debug("Anthropic stream cache: read=%d tokens", cache_read)
            except Exception:
                pass

    def is_available(self) -> bool:
        return bool(settings.anthropic_api_key)
