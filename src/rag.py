from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from src.config import Settings, settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KnowledgeChunk:
    source: str
    text: str


@dataclass(frozen=True)
class RetrievedChunk:
    source: str
    text: str
    similarity: float
    metadata: dict[str, object]


def _split_into_chunks(text: str, source: str) -> list[KnowledgeChunk]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    if not blocks:
        return []
    return [KnowledgeChunk(source=source, text=block) for block in blocks]


def load_knowledge(knowledge_dir: Path) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    if not knowledge_dir.exists():
        return chunks

    for path in sorted(knowledge_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".txt", ".md"}:
            continue
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        source = str(path.relative_to(knowledge_dir)).replace("\\", "/")
        chunks.extend(_split_into_chunks(text, source))

    return chunks


def _tokenize(text: str) -> set[str]:
    return {word for word in re.findall(r"[а-яёa-z0-9]+", text.lower()) if len(word) > 2}


def _keyword_score(query: str, chunk: KnowledgeChunk) -> float:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0
    chunk_tokens = _tokenize(chunk.text)
    overlap = len(query_tokens & chunk_tokens)
    return overlap / len(query_tokens)


def _score_chunk(query: str, chunk: KnowledgeChunk) -> int:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0
    chunk_tokens = _tokenize(chunk.text)
    return len(query_tokens & chunk_tokens)


def format_retrieved_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "Контекст не найден. База знаний пуста."

    parts = []
    for chunk in chunks:
        doc_type = chunk.metadata.get("doc_type", "general")
        parts.append(
            f"[{chunk.source} | {doc_type} | score: {chunk.similarity:.2f}]\n{chunk.text}"
        )
    return "\n\n---\n\n".join(parts)


def format_retrieval_log(
    chunks: list[RetrievedChunk],
    *,
    preview_chars: int = 100,
) -> str:
    if not chunks:
        return "none"

    parts: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        doc_type = chunk.metadata.get("doc_type", "general")
        preview = " ".join(chunk.text.split())[:preview_chars]
        parts.append(
            f"{index}:{chunk.source}/{doc_type} score={chunk.similarity:.3f} "
            f"preview={preview!r}"
        )
    return " | ".join(parts)


class KnowledgeRetriever:
    def __init__(self, config: Settings | None = None) -> None:
        self._config = config or settings
        self._local_chunks = load_knowledge(self._config.knowledge_dir)
        self._client = None
        self._embeddings = None

        if self._is_vector_configured():
            try:
                from src.rag_index import create_embeddings, create_supabase_client

                self._client = create_supabase_client(self._config)
                self._embeddings = create_embeddings(self._config)
                logger.info("Vector RAG enabled (Supabase pgvector)")
            except ValueError as exc:
                logger.warning("Vector RAG disabled: %s", exc)
        else:
            logger.info("Vector RAG disabled: missing Supabase/OpenAI credentials")

    def _is_vector_configured(self) -> bool:
        return bool(
            self._config.supabase_url
            and self._config.supabase_service_role_key
            and self._config.openai_api_key
        )

    @property
    def local_chunks(self) -> list[KnowledgeChunk]:
        return self._local_chunks

    @property
    def vector_enabled(self) -> bool:
        return self._client is not None and self._embeddings is not None

    def search(self, query: str, max_chunks: int | None = None) -> list[RetrievedChunk]:
        limit = max_chunks or self._config.max_rag_chunks
        if self.vector_enabled:
            try:
                return self._vector_search(query, limit)
            except Exception:
                logger.warning("Vector search failed, using keyword fallback", exc_info=True)
        return self._keyword_search(query, limit)

    def retrieve_context(self, query: str, max_chunks: int | None = None) -> str:
        return format_retrieved_context(self.search(query, max_chunks))

    def best_score(self, query: str, max_chunks: int | None = None) -> float:
        results = self.search(query, max_chunks)
        if not results:
            return 0.0
        return results[0].similarity

    def is_relevant(self, query: str, max_chunks: int | None = None) -> bool:
        return self.best_score(query, max_chunks) >= self._config.rag_similarity_threshold

    def _vector_search(self, query: str, limit: int) -> list[RetrievedChunk]:
        assert self._embeddings is not None
        assert self._client is not None

        embedding = self._embeddings.embed_query(query)
        response = self._client.rpc(
            "match_knowledge_chunks",
            {
                "query_embedding": embedding,
                "match_count": limit,
                "filter": {},
            },
        ).execute()

        results: list[RetrievedChunk] = []
        for row in response.data or []:
            metadata = row.get("metadata") or {}
            source = str(metadata.get("source") or "unknown")
            results.append(
                RetrievedChunk(
                    source=source,
                    text=row["content"],
                    similarity=float(row["similarity"]),
                    metadata=metadata,
                )
            )
        return results

    def _keyword_search(self, query: str, limit: int) -> list[RetrievedChunk]:
        ranked = sorted(
            self._local_chunks,
            key=lambda chunk: (_keyword_score(query, chunk), len(chunk.text)),
            reverse=True,
        )
        selected = ranked[:limit]

        return [
            RetrievedChunk(
                source=chunk.source,
                text=chunk.text,
                similarity=_keyword_score(query, chunk),
                metadata={"source": chunk.source, "doc_type": "keyword_fallback"},
            )
            for chunk in selected
            if _keyword_score(query, chunk) > 0
        ] or [
            RetrievedChunk(
                source=chunk.source,
                text=chunk.text,
                similarity=0.0,
                metadata={"source": chunk.source, "doc_type": "keyword_fallback"},
            )
            for chunk in ranked[:limit]
        ]


def best_chunk_score(query: str, chunks: list[KnowledgeChunk]) -> int:
    if not chunks:
        return 0
    return max(int(_keyword_score(query, chunk) * len(_tokenize(query))) for chunk in chunks)


def retrieve_context(
    query: str,
    chunks: list[KnowledgeChunk],
    max_chunks: int = 5,
) -> str:
    ranked = sorted(
        chunks,
        key=lambda chunk: (_keyword_score(query, chunk), len(chunk.text)),
        reverse=True,
    )
    selected = ranked[:max_chunks]
    retrieved = [
        RetrievedChunk(
            source=chunk.source,
            text=chunk.text,
            similarity=_keyword_score(query, chunk),
            metadata={"source": chunk.source},
        )
        for chunk in selected
    ]
    return format_retrieved_context(retrieved)
