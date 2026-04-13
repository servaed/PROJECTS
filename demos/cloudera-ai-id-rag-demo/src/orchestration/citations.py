"""Citation assembler — formats document sources and SQL trace for the UI.

Citations are always shown to the user for transparency and explainability.
Never invent citations; only emit what was actually retrieved.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.retrieval.retriever import RetrievedChunk
from src.sql.executor import QueryResult


@dataclass
class DocumentCitation:
    title: str
    source_path: str
    chunk_index: int
    excerpt: str          # short snippet shown in UI
    ingest_timestamp: str


@dataclass
class SqlCitation:
    sql: str
    row_count: int
    latency_ms: float
    table_markdown: str   # first N rows as markdown table


def build_document_citations(chunks: list[RetrievedChunk], excerpt_length: int = 300) -> list[DocumentCitation]:
    seen_paths: set[str] = set()
    citations: list[DocumentCitation] = []
    for chunk in chunks:
        key = f"{chunk.source_path}:{chunk.chunk_index}"
        if key in seen_paths:
            continue
        seen_paths.add(key)
        excerpt = chunk.text[:excerpt_length].replace("\n", " ").strip()
        if len(chunk.text) > excerpt_length:
            excerpt += "…"
        citations.append(
            DocumentCitation(
                title=chunk.title,
                source_path=chunk.source_path,
                chunk_index=chunk.chunk_index,
                excerpt=excerpt,
                ingest_timestamp=chunk.ingest_timestamp,
            )
        )
    return citations


def build_sql_citation(result: QueryResult) -> SqlCitation | None:
    if result is None or result.error:
        return None
    return SqlCitation(
        sql=result.sql,
        row_count=result.row_count,
        latency_ms=result.latency_ms,
        table_markdown=result.to_markdown_table(max_rows=10),
    )
