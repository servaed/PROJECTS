"""Application configuration — all values loaded from environment variables."""

import os
import pathlib
import warnings
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator
from typing import Literal


def _load_override_env(path: str = "data/.env.local") -> None:
    """Load key=value pairs from the configure-wizard override file into os.environ.

    Mirrors what deployment/launch_app.sh does via `source data/.env.local`.
    Must run before Settings() is instantiated so that the live-reading properties
    (llm_base_url, llm_api_key, llm_model_id) see the correct values on startup.

    Platform env vars (already in os.environ) are never overwritten — the file
    only fills in keys that are absent, preserving Cloudera AI platform precedence.
    """
    p = pathlib.Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


_load_override_env()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "data/.env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM Provider ──────────────────────────────────────────────────────
    # "cloudera"  : Cloudera AI Inference (OpenAI-compatible endpoint)
    # "openai"    : OpenAI API directly
    # "azure"     : Azure OpenAI
    # "bedrock"   : Amazon Bedrock (Converse API, any supported model)
    # "anthropic" : Anthropic API directly
    # "local"     : Any local OpenAI-compatible server (Ollama, LM Studio, vLLM)
    llm_provider: Literal["cloudera", "openai", "azure", "bedrock", "anthropic", "local"] = "cloudera"

    # ── Cloudera AI Inference ─────────────────────────────────────────────
    cloudera_inference_url: str = ""
    cloudera_inference_api_key: str = ""
    cloudera_inference_model_id: str = "meta-llama-3-8b-instruct"

    # ── OpenAI ────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model_id: str = "gpt-4o"

    # ── Azure OpenAI ──────────────────────────────────────────────────────
    azure_openai_endpoint: str = ""          # https://your-resource.openai.azure.com
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-02-01"
    azure_openai_deployment: str = "gpt-4o"  # deployment name (not model name)

    # ── Amazon Bedrock ────────────────────────────────────────────────────
    # Uses the Bedrock Converse API — works with Claude, Llama, Titan, Mistral, etc.
    bedrock_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    bedrock_access_key: str = ""           # leave empty to use instance role / profile
    bedrock_secret_key: str = ""
    bedrock_session_token: str = ""        # for temporary credentials (STS)
    bedrock_profile: str = ""              # AWS named profile (e.g. "prod", "staging")

    # ── Anthropic (direct) ────────────────────────────────────────────────
    anthropic_api_key: str = ""
    anthropic_model_id: str = "claude-3-5-sonnet-20241022"

    # ── Local / Ollama / vLLM / LM Studio ────────────────────────────────
    local_llm_url: str = "http://localhost:11434/v1"
    local_llm_model_id: str = "llama3"
    local_llm_api_key: str = "no-key"      # most local servers ignore this

    # ── Embeddings ────────────────────────────────────────────────────────
    embeddings_provider: Literal["local", "openai"] = "local"
    embeddings_model: str = "intfloat/multilingual-e5-large"

    # ── Vector store ──────────────────────────────────────────────────────
    vector_store_type: Literal["faiss"] = "faiss"
    vector_store_path: str = "./data/vector_store"

    # ── Document storage ──────────────────────────────────────────────────
    docs_source_path: str = "./data/sample_docs"
    docs_storage_type: Literal["local", "hdfs", "s3"] = "local"
    hdfs_url: str = "http://namenode:9870"
    hdfs_user: str = "hdfs"
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # ── Query engine ──────────────────────────────────────────────────────
    # "sqlite" : embedded SQLite (local dev, backwards-compatible default)
    # "trino"  : Trino coordinator (Docker image / CDP CDW)
    query_engine: Literal["sqlite", "trino"] = "sqlite"

    # ── Trino ─────────────────────────────────────────────────────────────
    trino_host: str = "localhost"
    trino_port: int = 8085
    trino_catalog: str = "iceberg"
    trino_schema: str = "demo"
    trino_user: str = "admin"

    # ── MinIO / Ozone object storage ──────────────────────────────────────
    # minio_endpoint: http://localhost:9000 for local Docker; replace with
    # Ozone S3 Gateway URL (e.g. http://ozone-s3gw:9878) on a real CDP cluster.
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_docs_bucket: str = "rag-docs"
    minio_warehouse_bucket: str = "rag-warehouse"

    # ── SQL ───────────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./data/sample_tables/demo.db"
    sql_approved_tables: str = "kredit_umkm,nasabah,cabang"
    sql_max_rows: int = Field(default=500, ge=1, le=1000)

    # ── Application ───────────────────────────────────────────────────────
    app_port: int = 8080
    app_title: str = "Asisten Enterprise Cloudera AI"
    log_level: str = "INFO"
    history_path: str = "./.claude/history"

    # ── Cross-field validation ────────────────────────────────────────────

    @model_validator(mode="after")
    def _validate_s3_consistency(self) -> "Settings":
        """Warn when docs_storage_type=s3 but required S3 settings are absent."""
        if self.docs_storage_type == "s3":
            missing = [
                f for f in ("s3_endpoint_url", "s3_bucket", "s3_access_key", "s3_secret_key")
                if not getattr(self, f)
            ]
            if missing:
                warnings.warn(
                    f"docs_storage_type=s3 but these S3 settings are empty: {missing}. "
                    "Document loading will fail until they are configured.",
                    stacklevel=2,
                )
        return self

    def __repr__(self) -> str:
        """Mask sensitive fields to prevent credential leakage in logs/tracebacks."""
        safe: dict = {}
        for k, v in self.model_dump().items():
            if v and any(tok in k.upper() for tok in ("KEY", "SECRET", "PASSWORD", "TOKEN")):
                safe[k] = "●●●●●●●●"
            else:
                safe[k] = v
        return f"Settings({safe})"

    __str__ = __repr__

    # ── Derived properties ────────────────────────────────────────────────

    @property
    def approved_tables(self) -> list[str]:
        if not self.sql_approved_tables.strip():
            return []
        return [t.strip() for t in self.sql_approved_tables.split(",") if t.strip()]

    @property
    def _live_provider(self) -> str:
        """Current LLM provider — reads live os.environ so configure changes take effect
        immediately without a restart."""
        return os.environ.get("LLM_PROVIDER", self.llm_provider)

    @property
    def llm_base_url(self) -> str:
        """Base URL for OpenAI-compatible providers (not used for Bedrock/Anthropic).

        Checks generic LLM_BASE_URL env var first (written by the /configure wizard),
        then falls back to provider-specific env vars.  Reads os.environ live so that
        POST /api/configure changes are reflected immediately.
        """
        # Generic override written by /configure wizard
        if os.environ.get("LLM_BASE_URL"):
            return os.environ["LLM_BASE_URL"]
        provider = self._live_provider
        if provider == "cloudera":
            return os.environ.get("CLOUDERA_INFERENCE_URL", self.cloudera_inference_url)
        if provider == "openai":
            return "https://api.openai.com/v1"
        if provider == "azure":
            return os.environ.get("AZURE_OPENAI_ENDPOINT", self.azure_openai_endpoint)
        if provider == "local":
            return os.environ.get("LOCAL_LLM_URL", self.local_llm_url)
        return ""  # bedrock / anthropic use their own SDKs

    @property
    def llm_api_key(self) -> str:
        # Generic override written by /configure wizard
        if os.environ.get("LLM_API_KEY"):
            return os.environ["LLM_API_KEY"]
        provider = self._live_provider
        if provider == "cloudera":
            return os.environ.get("CLOUDERA_INFERENCE_API_KEY", self.cloudera_inference_api_key)
        if provider == "openai":
            return os.environ.get("OPENAI_API_KEY", self.openai_api_key)
        if provider == "azure":
            return os.environ.get("AZURE_OPENAI_API_KEY", self.azure_openai_api_key)
        if provider == "local":
            return os.environ.get("LOCAL_LLM_API_KEY", self.local_llm_api_key)
        return ""

    @property
    def llm_model_id(self) -> str:
        # Generic override written by /configure wizard
        if os.environ.get("LLM_MODEL_ID"):
            return os.environ["LLM_MODEL_ID"]
        provider = self._live_provider
        if provider == "cloudera":
            return os.environ.get("CLOUDERA_INFERENCE_MODEL_ID", self.cloudera_inference_model_id)
        if provider == "openai":
            return os.environ.get("OPENAI_MODEL_ID", self.openai_model_id)
        if provider == "azure":
            return os.environ.get("AZURE_OPENAI_DEPLOYMENT", self.azure_openai_deployment)
        if provider == "bedrock":
            return os.environ.get("BEDROCK_MODEL_ID", self.bedrock_model_id)
        if provider == "anthropic":
            return os.environ.get("ANTHROPIC_MODEL_ID", self.anthropic_model_id)
        if provider == "local":
            return os.environ.get("LOCAL_LLM_MODEL_ID", self.local_llm_model_id)
        return ""


# Singleton — import this everywhere
settings = Settings()
