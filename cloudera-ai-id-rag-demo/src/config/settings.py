"""Application configuration — all values loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    llm_provider: Literal["cloudera", "openai", "local"] = "cloudera"
    cloudera_inference_url: str = ""
    cloudera_inference_api_key: str = ""
    cloudera_inference_model_id: str = "meta-llama-3-8b-instruct"
    openai_api_base: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model_id: str = "gpt-4o"

    # Embeddings
    embeddings_provider: Literal["local", "openai"] = "local"
    embeddings_model: str = "intfloat/multilingual-e5-base"

    # Vector store
    vector_store_type: Literal["faiss"] = "faiss"
    vector_store_path: str = "./data/vector_store"

    # Document storage
    docs_source_path: str = "./data/sample_docs"
    docs_storage_type: Literal["local", "hdfs", "s3"] = "local"
    hdfs_url: str = "http://namenode:9870"
    hdfs_user: str = "hdfs"
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # SQL
    database_url: str = "sqlite:///./data/sample_tables/demo.db"
    sql_approved_tables: str = "kredit_umkm,nasabah,cabang"
    sql_max_rows: int = Field(default=500, ge=1, le=1000)

    # Application
    app_port: int = 8080
    app_title: str = "Asisten Enterprise Cloudera AI"
    log_level: str = "INFO"
    history_path: str = "./.claude/history"

    @property
    def approved_tables(self) -> list[str]:
        """Return approved table names as a list."""
        if not self.sql_approved_tables.strip():
            return []
        return [t.strip() for t in self.sql_approved_tables.split(",") if t.strip()]

    @property
    def llm_base_url(self) -> str:
        if self.llm_provider == "cloudera":
            return self.cloudera_inference_url
        return self.openai_api_base

    @property
    def llm_api_key(self) -> str:
        if self.llm_provider == "cloudera":
            return self.cloudera_inference_api_key
        return self.openai_api_key

    @property
    def llm_model_id(self) -> str:
        if self.llm_provider == "cloudera":
            return self.cloudera_inference_model_id
        return self.openai_model_id


# Singleton — import this everywhere
settings = Settings()
