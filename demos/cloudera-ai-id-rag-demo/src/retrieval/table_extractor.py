"""PDF table extractor — Document Intelligence feature.

Extracts tabular data from uploaded PDFs using pdfplumber and registers
them as queryable DuckDB views with a 'doc_' prefix.

Falls back gracefully when pdfplumber is not installed.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from src.config.logging import get_logger

if TYPE_CHECKING:
    import pandas as pd

logger = get_logger(__name__)

try:
    import pdfplumber
    _PDFPLUMBER_OK = True
except ImportError:
    _PDFPLUMBER_OK = False
    logger.warning("pdfplumber not installed — PDF table extraction disabled. Run: pip install pdfplumber")


def extract_tables_from_pdf(pdf_path: str | Path) -> list[dict]:
    """Extract all tables from a PDF file.

    Returns a list of dicts:
      {name: str, df: pd.DataFrame, page: int, row_count: int, col_count: int}

    Returns an empty list when pdfplumber is unavailable or no tables found.
    """
    if not _PDFPLUMBER_OK:
        return []

    import pandas as pd

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        logger.error("PDF not found: %s", pdf_path)
        return []

    results = []
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                raw_tables = page.extract_tables()
                for tbl_num, raw in enumerate(raw_tables, 1):
                    if not raw or len(raw) < 2:
                        continue
                    # First row as headers; sanitise column names
                    headers = [
                        re.sub(r"\s+", "_", str(h or f"col_{i}").strip().lower())[:40]
                        for i, h in enumerate(raw[0])
                    ]
                    # Deduplicate column names
                    seen: dict[str, int] = {}
                    clean_headers: list[str] = []
                    for h in headers:
                        if h in seen:
                            seen[h] += 1
                            clean_headers.append(f"{h}_{seen[h]}")
                        else:
                            seen[h] = 0
                            clean_headers.append(h)

                    rows = [[str(c or "").strip() for c in row] for row in raw[1:]]
                    df = pd.DataFrame(rows, columns=clean_headers)
                    # Try numeric coercion on each column
                    for col in df.columns:
                        try:
                            df[col] = pd.to_numeric(
                                df[col].str.replace(",", "", regex=False), errors="ignore"
                            )
                        except Exception:
                            pass

                    results.append({
                        "name": f"p{page_num}_t{tbl_num}",
                        "df": df,
                        "page": page_num,
                        "row_count": len(df),
                        "col_count": len(clean_headers),
                    })

    except Exception as exc:
        logger.error("PDF table extraction failed for %s: %s", pdf_path, exc)

    logger.info("Extracted %d table(s) from %s", len(results), pdf_path.name)
    return results


def register_tables_as_views(
    tables: list[dict],
    doc_stem: str,
    parquet_dir: str | Path,
) -> list[str]:
    """Save extracted tables as Parquet files and register DuckDB views.

    Returns the list of view names that were registered.
    """
    if not tables:
        return []

    import pyarrow as pa
    import pyarrow.parquet as pq
    from src.connectors.duckdb_adapter import _get_conn  # shared DuckDB connection

    parquet_dir = Path(parquet_dir)
    parquet_dir.mkdir(parents=True, exist_ok=True)

    # Sanitise doc name for use as SQL identifier prefix
    safe_stem = re.sub(r"[^a-z0-9]", "_", doc_stem.lower())[:24].strip("_")

    registered: list[str] = []
    try:
        conn = _get_conn()
        for t in tables:
            view_name = f"doc_{safe_stem}_{t['name']}"
            out_path  = parquet_dir / f"{view_name}.parquet"
            arrow_tbl = pa.Table.from_pandas(t["df"], preserve_index=False)
            pq.write_table(arrow_tbl, out_path)
            conn.execute(
                f"CREATE OR REPLACE VIEW {view_name} AS "
                f"SELECT * FROM read_parquet('{out_path.as_posix()}')"
            )
            registered.append(view_name)
            logger.info(
                "Registered view %s (%d rows, %d cols) from page %d",
                view_name, t["row_count"], t["col_count"], t["page"],
            )
    except Exception as exc:
        logger.error("Failed to register DuckDB views: %s", exc)

    return registered
