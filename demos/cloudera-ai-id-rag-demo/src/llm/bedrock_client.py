"""Amazon Bedrock LLM client — uses the Bedrock Converse API.

The Converse API provides a unified message format across all Bedrock model
families (Anthropic Claude, Meta Llama, Mistral, Amazon Titan, Cohere, etc.)
so you can switch models by changing BEDROCK_MODEL_ID without code changes.

Credentials are resolved in this order (standard AWS SDK chain):
  1. BEDROCK_ACCESS_KEY + BEDROCK_SECRET_KEY env vars (explicit)
  2. BEDROCK_PROFILE  (named AWS profile in ~/.aws/credentials)
  3. Environment variables AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
  4. IAM instance role / ECS task role / EKS service account (recommended for production)

Install: pip install boto3
"""

from __future__ import annotations

from collections.abc import Generator

import boto3

from src.llm.base import BaseLLMClient, LLMResponse
from src.config.settings import settings
from src.config.logging import get_logger

logger = get_logger(__name__)


class BedrockClient(BaseLLMClient):
    """Amazon Bedrock LLM client via the Converse / ConversStream API."""

    def __init__(self) -> None:
        self._model = settings.bedrock_model_id
        self._client = self._build_client()
        logger.info(
            "LLM provider: Amazon Bedrock — region=%s, model=%s",
            settings.bedrock_region,
            self._model,
        )

    def _build_client(self):
        region = settings.bedrock_region or "us-east-1"

        # Explicit credentials take priority
        if settings.bedrock_access_key and settings.bedrock_secret_key:
            kwargs: dict = {
                "region_name": region,
                "aws_access_key_id": settings.bedrock_access_key,
                "aws_secret_access_key": settings.bedrock_secret_key,
            }
            if settings.bedrock_session_token:
                kwargs["aws_session_token"] = settings.bedrock_session_token
            return boto3.client("bedrock-runtime", **kwargs)

        # Named profile (uses ~/.aws/credentials)
        if settings.bedrock_profile:
            session = boto3.Session(profile_name=settings.bedrock_profile)
            return session.client("bedrock-runtime", region_name=region)

        # Fall through to SDK default chain (env vars, instance role, etc.)
        return boto3.client("bedrock-runtime", region_name=region)

    # ── Internal helpers ───────────────────────────────────────────────────

    @staticmethod
    def _to_converse_messages(messages: list[dict]) -> tuple[str, list[dict]]:
        """Split OpenAI-format messages into (system_text, converse_messages).

        The Converse API keeps the system prompt separate from the message list
        and wraps each message content in a list of content blocks.
        """
        system_parts: list[str] = []
        converse: list[dict] = []

        for m in messages:
            role = m["role"]
            content = m.get("content") or ""
            if role == "system":
                system_parts.append(content)
            else:
                converse.append(
                    {
                        "role": role,  # "user" or "assistant"
                        "content": [{"text": content}],
                    }
                )

        return "\n\n".join(system_parts), converse

    def _base_kwargs(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> dict:
        system_text, converse_messages = self._to_converse_messages(messages)
        kwargs: dict = {
            "modelId": self._model,
            "messages": converse_messages,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system_text:
            kwargs["system"] = [{"text": system_text}]
        return kwargs

    # ── BaseLLMClient interface ────────────────────────────────────────────

    def chat(
        self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 1024
    ) -> LLMResponse:
        logger.debug("Bedrock request: model=%s, messages=%d", self._model, len(messages))
        kwargs = self._base_kwargs(messages, temperature, max_tokens)
        response = self._client.converse(**kwargs)

        content = response["output"]["message"]["content"][0]["text"]
        usage = response.get("usage", {})
        return LLMResponse(
            content=content,
            model=self._model,
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
        )

    def stream_chat(
        self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 1024
    ) -> Generator[str, None, None]:
        logger.debug("Bedrock stream: model=%s, messages=%d", self._model, len(messages))
        kwargs = self._base_kwargs(messages, temperature, max_tokens)
        response = self._client.converse_stream(**kwargs)

        for event in response["stream"]:
            if "contentBlockDelta" in event:
                delta = event["contentBlockDelta"].get("delta", {})
                text = delta.get("text")
                if text:
                    yield text

    def is_available(self) -> bool:
        return bool(settings.bedrock_region and settings.bedrock_model_id)
