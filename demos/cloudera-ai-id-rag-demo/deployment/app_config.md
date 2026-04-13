# Environment Variable Reference

All configuration is loaded from environment variables.
For local development, copy `.env.example` to `.env`.
For CML deployment, set these in the Application **Environment Variables** panel.

See `DEPLOYMENT.md` for the full deployment guide.

---

## LLM Provider

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_PROVIDER` | Yes | `cloudera` | `cloudera` / `openai` / `azure` / `bedrock` / `anthropic` / `local` |

### Cloudera AI Inference

| Variable | Required | Default | Description |
|---|---|---|---|
| `CLOUDERA_INFERENCE_URL` | If cloudera | — | Full endpoint URL from AI Inference service |
| `CLOUDERA_INFERENCE_API_KEY` | If cloudera | — | API key from the endpoint detail page |
| `CLOUDERA_INFERENCE_MODEL_ID` | No | `meta-llama-3-8b-instruct` | Model name |

### OpenAI

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | If openai | — | `sk-...` API key |
| `OPENAI_MODEL_ID` | No | `gpt-4o` | Model name |

### Azure OpenAI

| Variable | Required | Default | Description |
|---|---|---|---|
| `AZURE_OPENAI_ENDPOINT` | If azure | — | `https://resource.openai.azure.com` |
| `AZURE_OPENAI_API_KEY` | If azure | — | Azure API key |
| `AZURE_OPENAI_DEPLOYMENT` | No | `gpt-4o` | Deployment name (not model name) |
| `AZURE_OPENAI_API_VERSION` | No | `2024-02-01` | API version string |

### Amazon Bedrock

| Variable | Required | Default | Description |
|---|---|---|---|
| `BEDROCK_REGION` | If bedrock | `us-east-1` | AWS region where Bedrock is enabled |
| `BEDROCK_MODEL_ID` | If bedrock | `anthropic.claude-3-sonnet-20240229-v1:0` | Bedrock model ID |
| `BEDROCK_ACCESS_KEY` | No | — | AWS access key (leave empty to use instance role) |
| `BEDROCK_SECRET_KEY` | No | — | AWS secret key |
| `BEDROCK_SESSION_TOKEN` | No | — | STS temporary session token |
| `BEDROCK_PROFILE` | No | — | Named AWS profile (`~/.aws/credentials`) |

### Anthropic (direct)

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | If anthropic | — | `sk-ant-...` API key |
| `ANTHROPIC_MODEL_ID` | No | `claude-3-5-sonnet-20241022` | Claude model name |

### Local (Ollama / LM Studio / vLLM)

| Variable | Required | Default | Description |
|---|---|---|---|
| `LOCAL_LLM_URL` | If local | `http://localhost:11434/v1` | Base URL of local server |
| `LOCAL_LLM_MODEL_ID` | No | `llama3` | Model name as known to the local server |
| `LOCAL_LLM_API_KEY` | No | `no-key` | API key (most local servers ignore this) |

---

## Embeddings

| Variable | Required | Default | Description |
|---|---|---|---|
| `EMBEDDINGS_PROVIDER` | No | `local` | `local` (sentence-transformers) or `openai` |
| `EMBEDDINGS_MODEL` | No | `intfloat/multilingual-e5-base` | Model name or HuggingFace ID |

---

## Vector Store

| Variable | Required | Default | Description |
|---|---|---|---|
| `VECTOR_STORE_TYPE` | No | `faiss` | Vector store backend (only `faiss` in demo) |
| `VECTOR_STORE_PATH` | No | `./data/vector_store` | Directory for FAISS index files |

---

## Document Storage

| Variable | Required | Default | Description |
|---|---|---|---|
| `DOCS_SOURCE_PATH` | No | `./data/sample_docs` | Source document directory or URI |
| `DOCS_STORAGE_TYPE` | No | `local` | `local`, `hdfs`, or `s3` |
| `HDFS_URL` | If hdfs | `http://namenode:9870` | HDFS WebHDFS endpoint |
| `HDFS_USER` | If hdfs | `hdfs` | HDFS user |
| `S3_ENDPOINT_URL` | If s3 | — | S3-compatible endpoint |
| `S3_BUCKET` | If s3 | — | Bucket name |
| `S3_ACCESS_KEY` | If s3 | — | S3 access key |
| `S3_SECRET_KEY` | If s3 | — | S3 secret key |

---

## SQL / Database

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | No | SQLite demo | SQLAlchemy connection URL |
| `SQL_APPROVED_TABLES` | No | `kredit_umkm,nasabah,cabang` | Comma-separated table allowlist |
| `SQL_MAX_ROWS` | No | `500` | Max rows per SQL result (hard cap: 1000) |

---

## Application

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_PORT` | No | `8080` | **Must be 8080** for Cloudera AI Applications |
| `APP_TITLE` | No | `Asisten Enterprise Cloudera AI` | Window title |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
