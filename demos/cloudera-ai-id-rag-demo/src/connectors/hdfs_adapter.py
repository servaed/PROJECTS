"""HDFS adapter stub for Cloudera-managed document storage.

In demo mode this is not invoked — set DOCS_STORAGE_TYPE=hdfs to activate.
In production, install hdfs3 or use WebHDFS REST API via httpx.
"""

from pathlib import PurePosixPath
from src.config.settings import settings
from src.config.logging import get_logger

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".html", ".md"}


class HdfsAdapter:
    """Read documents from HDFS using the WebHDFS REST API."""

    def __init__(self) -> None:
        self.hdfs_url = settings.hdfs_url.rstrip("/")
        self.user = settings.hdfs_user
        self.base_path = settings.docs_source_path

    def list_documents(self) -> list[str]:
        """Return HDFS paths for all supported documents under base_path."""
        import httpx

        list_url = f"{self.hdfs_url}/webhdfs/v1{self.base_path}?op=LISTSTATUS&user.name={self.user}"
        try:
            resp = httpx.get(list_url, timeout=10)
            resp.raise_for_status()
            statuses = resp.json().get("FileStatuses", {}).get("FileStatus", [])
            paths = []
            for s in statuses:
                if s.get("type") == "FILE":
                    name = s["pathSuffix"]
                    if PurePosixPath(name).suffix.lower() in SUPPORTED_EXTENSIONS:
                        paths.append(f"{self.base_path}/{name}")
            logger.info("Found %d documents in HDFS %s", len(paths), self.base_path)
            return paths
        except Exception as exc:
            logger.error("HDFS list failed: %s", exc)
            return []

    def read_bytes(self, hdfs_path: str) -> bytes:
        import httpx

        url = f"{self.hdfs_url}/webhdfs/v1{hdfs_path}?op=OPEN&user.name={self.user}"
        resp = httpx.get(url, follow_redirects=True, timeout=30)
        resp.raise_for_status()
        return resp.content
