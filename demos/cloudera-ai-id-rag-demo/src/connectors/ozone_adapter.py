"""Ozone / MinIO adapter — S3-compatible object storage via boto3.

Used when settings.docs_storage_type == "s3".  The same code works against:
  - MinIO (Docker, local demo)
  - Apache Ozone S3 Gateway (CDP production)
  - Any S3-compatible endpoint

Exposes the same interface as FilesAdapter so document_loader can swap
adapters transparently.
"""

from __future__ import annotations

from pathlib import Path

import boto3
import botocore.config

from src.config.settings import settings
from src.config.logging import get_logger

logger = get_logger(__name__)

_SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".html", ".md"}


class OzoneAdapter:
    """Read documents from an S3-compatible bucket (MinIO or Ozone S3GW)."""

    def __init__(self, bucket: str | None = None) -> None:
        self._bucket = bucket or settings.minio_docs_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.minio_endpoint,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            region_name="us-east-1",
            config=botocore.config.Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )

    def list_documents(self) -> list[Path]:
        """List all supported document keys in the bucket.

        Returns relative Path objects (e.g. Path('banking/kebijakan_kredit.txt'))
        so that _infer_domain in document_loader works on the directory structure.
        """
        paginator = self._client.get_paginator("list_objects_v2")
        paths: list[Path] = []
        try:
            for page in paginator.paginate(Bucket=self._bucket):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    p = Path(key)
                    if p.suffix.lower() in _SUPPORTED_EXTENSIONS:
                        paths.append(p)
        except Exception as exc:
            logger.error("Failed to list objects in bucket '%s': %s", self._bucket, exc)
        logger.info("OzoneAdapter: found %d documents in s3://%s", len(paths), self._bucket)
        return paths

    def read_bytes(self, path: Path) -> bytes:
        """Download and return the raw bytes of a document."""
        key = str(path).replace("\\", "/")
        resp = self._client.get_object(Bucket=self._bucket, Key=key)
        return resp["Body"].read()
