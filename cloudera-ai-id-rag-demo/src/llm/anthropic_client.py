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
            kwargs["system"] = system_text
        return kwargs

    # ── BaseLLMClient interface ────────────────────────────────────────────

    def chat(
        self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 1024
    ) -> LLMResponse:
        logger.debug("Anthropic request: model=%s, messages=%d", self._model, len(messages))
        kwargs = self._build_kwargs(messages, temperature, max_tokens)
        response = self._client.messages.create(**kwargs)
        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def stream_chat(
        self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 1024
    ) -> Generator[str, None, None]:
        logger.debug("Anthropic stream: model=%s, messages=%d", self._model, len(messages))
        kwargs = self._build_kwargs(messages, temperature, max_tokens)
        with self._client.messages.stream(**kwargs) as stream:
            yield from stream.text_stream

    def is_available(self) -> bool:
        return bool(settings.anthropic_api_key)
