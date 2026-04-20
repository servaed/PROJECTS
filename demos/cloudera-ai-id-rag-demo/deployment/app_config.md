# Environment Variable Reference

All configuration is loaded from environment variables.
For local development, copy `.env.example` to `.env`.
For Docker / CML deployment, set these in the Application **Environment Variables** panel.

See `DEPLOYMENT.md` for the full deployment guide.

---

## LLM Provider

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_PROVIDER` | Yes | `cloudera` | `cloudera` / `openai` / `azure` / `bedrock` / `anthropic` / `local` |

### Cloudera AI Inference

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_BASE_URL` | Yes | — | Full endpoint URL from AI Inference service |
| `LLM_API_KEY` | Yes | — | API key from the endpoint detail page |
| `LLM_MODEL_ID` | No | `meta-llama-3-8b-instruct` | Model name |

### OpenAI

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_API_KEY` | Yes | — | `sk-...` API key |
| `LLM_MODEL_ID` | No | `gpt-4o` | Model name |

### Azure OpenAI

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_BASE_URL` | Yes | — | `https://resource.openai.azure.com/openai/deployments/gpt-4o` |
| `LLM_API_KEY` | Yes | — | Azure API key |
| `LLM_MODEL_ID` | No | `gpt-4o` | Deployment name |

### Amazon Bedrock

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_MODEL_ID` | Yes | — | Bedrock model ID (e.g. `anthropic.claude-3-5-sonnet-20241022-v2:0`) |
| `AWS_DEFAULT_REGION` | Yes | `us-east-1` | AWS region |
| `AWS_ACCESS_KEY_ID` | No | — | Leave empty to use IAM instance role |
| `AWS_SECRET_ACCESS_KEY` | No | — | AWS secret key |

### Anthropic (direct)

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_API_KEY` | Yes | — | `sk-ant-...` API key |
| `LLM_MODEL_ID` | No | `claude-3-5-sonnet-20241022` | Claude model name |

### Local (Ollama / LM Studio / vLLM)

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_BASE_URL` | Yes | `http://localhost:11434/v1` | Base URL of local server |
| `LLM_MODEL_ID` | No | `llama3` | Model name as known to the local server |
| `LLM_API_KEY` | No | `no-key` | API key (most local servers ignore this) |

---

## Embeddings

| Variable | Required | Default | Description |
|---|---|---|---|
| `EMBEDDINGS_PROVIDER` | No | `local` | `local` (sentence-transformers) or `openai` |
| `EMBEDDINGS_MODEL` | No | `intfloat/multilingual-e5-large` | Model name or HuggingFace ID |

---

## Vector Store

| Variable | Required | Default | Description |
|---|---|---|---|
| `VECTOR_STORE_TYPE` | No | `faiss` | Vector store backend (only `faiss` in demo) |
| `VECTOR_STORE_PATH` | No | `./data/vector_store` | Directory for FAISS index files |

---

## Query Engine

The demo supports two query engines. The Dockerfile sets `QUERY_ENGINE=trino` automatically.
Local dev defaults to `sqlite`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `QUERY_ENGINE` | No | `sqlite` | `sqlite` (local dev) or `trino` (Docker/CML) |

### Trino settings (when `QUERY_ENGINE=trino`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `TRINO_HOST` | If trino | `localhost` | Trino coordinator hostname |
| `TRINO_PORT` | If trino | `8085` | Trino HTTP port |
| `TRINO_CATALOG` | If trino | `iceberg` | Catalog name in Trino (Iceberg connector) |
| `TRINO_SCHEMA` | If trino | `demo` | Schema within the catalog |
| `TRINO_USER` | If trino | `admin` | Trino username |

For CDP production, point `TRINO_HOST` to your Cloudera Data Warehouse (CDW) endpoint.

### SQLite settings (when `QUERY_ENGINE=sqlite`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | No | `sqlite:///./data/sample_tables/demo.db` | SQLAlchemy connection URL |
| `SQL_APPROVED_TABLES` | No | all 9 demo tables | Comma-separated table allowlist |
| `SQL_MAX_ROWS` | No | `500` | Max rows per SQL result (hard cap: 1000) |

---

## Document Storage

Two storage backends are supported. The Dockerfile sets `DOCS_STORAGE_TYPE=s3` automatically.
Local dev defaults to `local`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DOCS_STORAGE_TYPE` | No | `local` | `local`, `hdfs`, or `s3` |
| `DOCS_SOURCE_PATH` | No | `./data/sample_docs` | Used when `DOCS_STORAGE_TYPE=local` |

### MinIO / Ozone settings (when `DOCS_STORAGE_TYPE=s3`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `MINIO_ENDPOINT` | If s3 | `http://localhost:9000` | S3-compatible endpoint URL |
| `MINIO_ACCESS_KEY` | If s3 | `minioadmin` | S3 access key |
| `MINIO_SECRET_KEY` | If s3 | `minioadmin` | S3 secret key |
| `MINIO_DOCS_BUCKET` | If s3 | `rag-docs` | Bucket containing source documents |
| `MINIO_WAREHOUSE_BUCKET` | If s3 | `rag-warehouse` | Iceberg table warehouse bucket |

For CDP production, set `MINIO_ENDPOINT` to your Ozone S3 Gateway URL
(e.g. `http://ozone-s3g.your-cluster:9878`) and update the access credentials.

### HDFS settings (when `DOCS_STORAGE_TYPE=hdfs`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `HDFS_URL` | If hdfs | `http://namenode:9870` | HDFS WebHDFS endpoint |
| `HDFS_USER` | If hdfs | `hdfs` | HDFS user |

---

## Application

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_PORT` | No | `8080` | **Must be 8080** for Cloudera AI Applications |
| `APP_TITLE` | No | `Asisten Enterprise Cloudera AI` | Window title |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
