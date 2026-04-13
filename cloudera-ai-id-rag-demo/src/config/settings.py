"""Application configuration — all values loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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
    embeddings_model: str = "intfloat/multilingual-e5-base"

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

    # ── SQL ───────────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./data/sample_tables/demo.db"
    sql_approved_tables: str = "kredit_umkm,nasabah,cabang"
    sql_max_rows: int = Field(default=500, ge=1, le=1000)

    # ── Application ───────────────────────────────────────────────────────
    app_port: int = 8080
    app_title: str = "Asisten Enterprise Cloudera AI"
    log_level: str = "INFO"
    history_path: str = "./.claude/history"

    # ── Derived properties ────────────────────────────────────────────────

    @property
    def approved_tables(self) -> list[str]:
        if not self.sql_approved_tables.strip():
            return []
        return [t.strip() for t in self.sql_approved_tables.split(",") if t.strip()]

    @property
    def llm_base_url(self) -> str:
        """Base URL for OpenAI-compatible providers (not used for Bedrock/Anthropic)."""
        if self.llm_provider == "cloudera":
            return self.cloudera_inference_url
        if self.llm_provider == "openai":
            return "https://api.openai.com/v1"
        if self.llm_provider == "azure":
            return self.azure_openai_endpoint
        if self.llm_provider == "local":
            return self.local_llm_url
        return ""  # bedrock / anthropic use their own SDKs

    @property
    def llm_api_key(self) -> str:
        if self.llm_provider == "cloudera":
            return self.cloudera_inference_api_key
        if self.llm_provider == "openai":
            return self.openai_api_key
        if self.llm_provider == "azure":
            return self.azure_openai_api_key
        if self.llm_provider == "local":
            return self.local_llm_api_key
        return ""

    @property
    def llm_model_id(self) -> str:
        if self.llm_provider == "cloudera":
            return self.cloudera_inference_model_id
        if self.llm_provider == "openai":
            return self.openai_model_id
        if self.llm_provider == "azure":
            return self.azure_openai_deployment
        if self.llm_provider == "bedrock":
            return self.bedrock_model_id
        if self.llm_provider == "anthropic":
            return self.anthropic_model_id
        if self.llm_provider == "local":
            return self.local_llm_model_id
        return ""


# Singleton — import this everywhere
settings = Settings()
