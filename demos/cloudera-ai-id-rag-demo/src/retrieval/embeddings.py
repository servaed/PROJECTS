"""Embeddings provider abstraction.

Demo default: sentence-transformers (local, no API key required).
Production: swap to OpenAI embeddings or Cloudera AI Inference embeddings
by changing EMBEDDINGS_PROVIDER in environment variables.
"""

from __future__ import annotations

from src.config.settings import settings
from src.config.logging import get_logger

logger = get_logger(__name__)

# Lazy-loaded model instance
_embeddings_instance = None


def get_embeddings():
    """Return a LangChain-compatible embeddings object based on configuration."""
    global _embeddings_instance
    if _embeddings_instance is not None:
        return _embeddings_instance

    if settings.embeddings_provider == "local":
        logger.info("Loading local embeddings model: %s", settings.embeddings_model)
        from langchain_community.embeddings import HuggingFaceEmbeddings

        _embeddings_instance = HuggingFaceEmbeddings(
            model_name=settings.embeddings_model,
            model_kwargs={
                "device": "cpu",
                # Prevent transformers from using meta tensors (accelerate device_map).
                # Without this, newer transformers versions initialise weights as meta
                # tensors and then fail with "Cannot copy out of meta tensor" when the
                # model is moved to CPU.
                "device_map": None,
                "low_cpu_mem_usage": False,
            },
            encode_kwargs={"normalize_embeddings": True},
        )
    elif settings.embeddings_provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        _embeddings_instance = OpenAIEmbeddings(
            openai_api_key=settings.openai_api_key,
            openai_api_base=settings.openai_api_base,
        )
    else:
        raise ValueError(f"Unknown embeddings provider: {settings.embeddings_provider}")

    return _embeddings_instance
