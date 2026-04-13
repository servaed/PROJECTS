"""Local filesystem adapter for document storage.

In production, swap this for the HDFS or S3 adapter without changing
the calling code — all adapters expose the same interface.
"""

from pathlib import Path
from src.config.logging import get_logger

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".html", ".md"}


class FilesAdapter:
    """Read documents from a local directory path."""

    def __init__(self, base_path: str) -> None:
        self.base_path = Path(base_path)

    def list_documents(self) -> list[Path]:
        """Return all supported document files under base_path recursively."""
        if not self.base_path.exists():
            logger.warning("Document source path does not exist: %s", self.base_path)
            return []
        files = [
            p for p in self.base_path.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        logger.info("Found %d documents in %s", len(files), self.base_path)
        return files

    def read_bytes(self, path: Path) -> bytes:
        return path.read_bytes()
