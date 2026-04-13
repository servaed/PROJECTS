"""Abstract LLM provider interface.

All LLM backends must implement this interface so they can be swapped
without changing orchestration or retrieval code.
"""

from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int


class BaseLLMClient(ABC):
    """Abstract base for all LLM provider clients."""

    @abstractmethod
    def chat(self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 1024) -> LLMResponse:
        """Send a chat completion request and return a structured response."""
        ...

    def stream_chat(
        self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 1024
    ) -> Generator[str, None, None]:
        """Stream tokens from a chat completion.

        Default implementation falls back to non-streaming for compatibility.
        Subclasses should override this for true streaming.
        """
        response = self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        yield response.content

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the backend is reachable and configured."""
        ...
