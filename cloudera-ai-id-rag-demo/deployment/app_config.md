# Environment Variable Reference

All configuration is loaded from environment variables.
Copy `.env.example` to `.env` for local development.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_PROVIDER` | Yes | `cloudera` | `cloudera`, `openai`, or `local` |
| `CLOUDERA_INFERENCE_URL` | If cloudera | — | Cloudera AI Inference endpoint URL |
| `CLOUDERA_INFERENCE_API_KEY` | If cloudera | — | Inference API key |
| `CLOUDERA_INFERENCE_MODEL_ID` | No | `meta-llama-3-8b-instruct` | Model ID |
| `EMBEDDINGS_PROVIDER` | No | `local` | `local` or `openai` |
| `EMBEDDINGS_MODEL` | No | `intfloat/multilingual-e5-base` | Embeddings model name |
| `VECTOR_STORE_PATH` | No | `./data/vector_store` | FAISS index storage path |
| `DOCS_SOURCE_PATH` | No | `./data/sample_docs` | Document source directory |
| `DOCS_STORAGE_TYPE` | No | `local` | `local`, `hdfs`, or `s3` |
| `DATABASE_URL` | No | SQLite demo | SQLAlchemy connection URL |
| `SQL_APPROVED_TABLES` | No | demo tables | Comma-separated list of allowed tables |
| `SQL_MAX_ROWS` | No | `500` | Maximum rows per query result |
| `APP_PORT` | No | `8080` | Application port — do NOT change |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
