from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from supabase import Client, create_client

from src.config import Settings, settings

logger = logging.getLogger(__name__)

_KNOWLEDGE_SUFFIXES = {".txt", ".md"}
_SKIP_KNOWLEDGE_NAMES = {"README.md", "catalog.yaml"}
_METADATA_FIELDS = (
    ("Тип", "doc_type"),
    ("Продукт", "product_name"),
    ("Уровень", "level"),
    ("Вопрос", "question"),
)


@dataclass(frozen=True)
class KnowledgeFileState:
    source: str
    file_hash: str
    chunk_count: int
    last_indexed_at: str


@dataclass(frozen=True)
class ReindexStats:
    scanned_files: int = 0
    indexed_files: int = 0
    skipped_files: int = 0
    removed_files: int = 0
    total_chunks: int = 0


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_text(path.read_text(encoding="utf-8"))


def _extract_metadata(
    text: str,
    *,
    source: str,
    chunk_index: int,
    file_hash: str,
    content_hash: str,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "source": source,
        "chunk_index": chunk_index,
        "file_hash": file_hash,
        "content_hash": content_hash,
    }

    for field_label, metadata_key in _METADATA_FIELDS:
        match = re.search(rf"^{re.escape(field_label)}:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
        if match:
            metadata[metadata_key] = match.group(1).strip().strip('"')

    if "doc_type" not in metadata:
        if re.search(r"^Вопрос:\s*", text, re.MULTILINE | re.IGNORECASE):
            metadata["doc_type"] = "faq"
        elif re.search(r"^Продукт:\s*", text, re.MULTILINE | re.IGNORECASE):
            metadata["doc_type"] = "product"
        elif source.endswith("faq.md"):
            metadata["doc_type"] = "faq"
        elif source.endswith("products.txt"):
            metadata["doc_type"] = "product"
        else:
            metadata["doc_type"] = "general"

    return metadata


def _split_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    if not blocks:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[str] = []
    for block in blocks:
        if len(block) <= chunk_size:
            chunks.append(block)
            continue
        chunks.extend(splitter.split_text(block))
    return chunks


def load_knowledge_documents(
    knowledge_dir: Path,
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> dict[str, list[Document]]:
    documents_by_source: dict[str, list[Document]] = {}

    if not knowledge_dir.exists():
        return documents_by_source

    for path in sorted(knowledge_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _KNOWLEDGE_SUFFIXES:
            continue
        if path.name in _SKIP_KNOWLEDGE_NAMES:
            continue

        source = str(path.relative_to(knowledge_dir)).replace("\\", "/")
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue

        file_hash = _sha256_text(text)
        chunks = _split_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        documents: list[Document] = []

        for chunk_index, chunk in enumerate(chunks):
            content_hash = _sha256_text(chunk)
            documents.append(
                Document(
                    page_content=chunk,
                    metadata=_extract_metadata(
                        chunk,
                        source=source,
                        chunk_index=chunk_index,
                        file_hash=file_hash,
                        content_hash=content_hash,
                    ),
                )
            )

        documents_by_source[source] = documents

    return documents_by_source


def create_supabase_client(config: Settings) -> Client:
    if not config.supabase_url or not config.supabase_service_role_key:
        raise ValueError(
            "SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY обязательны для индексации RAG."
        )
    return create_client(config.supabase_url, config.supabase_service_role_key)


def create_embeddings(config: Settings) -> OpenAIEmbeddings:
    if not config.openai_api_key:
        raise ValueError("OPENAI_API_KEY обязателен для генерации embeddings.")

    return OpenAIEmbeddings(
        model=config.rag_embedding_model,
        api_key=config.openai_api_key,
        dimensions=config.rag_embedding_dimensions,
    )


def fetch_indexed_files(client: Client) -> dict[str, KnowledgeFileState]:
    response = client.table("knowledge_files").select("*").execute()
    indexed: dict[str, KnowledgeFileState] = {}

    for row in response.data or []:
        indexed[row["source"]] = KnowledgeFileState(
            source=row["source"],
            file_hash=row["file_hash"],
            chunk_count=row["chunk_count"],
            last_indexed_at=row["last_indexed_at"],
        )
    return indexed


def _delete_file_index(client: Client, source: str) -> None:
    client.table("knowledge_files").delete().eq("source", source).execute()


def _insert_file_chunks(
    client: Client,
    *,
    source: str,
    file_hash: str,
    documents: list[Document],
    embeddings: OpenAIEmbeddings,
    batch_size: int,
) -> int:
    if not documents:
        _delete_file_index(client, source)
        return 0

    vectors = embeddings.embed_documents([doc.page_content for doc in documents])

    client.table("knowledge_files").upsert(
        {
            "source": source,
            "file_hash": file_hash,
            "chunk_count": len(documents),
            "last_indexed_at": datetime.now(UTC).isoformat(),
        }
    ).execute()

    rows = [
        {
            "source": source,
            "content": document.page_content,
            "metadata": document.metadata,
            "embedding": vector,
            "content_hash": document.metadata["content_hash"],
            "file_hash": file_hash,
            "is_active": True,
        }
        for document, vector in zip(documents, vectors, strict=True)
    ]

    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        client.table("knowledge_chunks").insert(batch).execute()

    return len(rows)


def _index_file(
    client: Client,
    *,
    source: str,
    documents: list[Document],
    embeddings: OpenAIEmbeddings,
    batch_size: int,
) -> int:
    file_hash = str(documents[0].metadata["file_hash"]) if documents else ""
    _delete_file_index(client, source)
    return _insert_file_chunks(
        client,
        source=source,
        file_hash=file_hash,
        documents=documents,
        embeddings=embeddings,
        batch_size=batch_size,
    )


def reindex_knowledge(
    *,
    config: Settings | None = None,
    force: bool = False,
) -> ReindexStats:
    config = config or settings
    knowledge_dir = config.knowledge_dir
    documents_by_source = load_knowledge_documents(
        knowledge_dir,
        chunk_size=config.rag_chunk_size,
        chunk_overlap=config.rag_chunk_overlap,
    )

    client = create_supabase_client(config)
    embeddings = create_embeddings(config)
    indexed_files = fetch_indexed_files(client)

    stats = ReindexStats(scanned_files=len(documents_by_source))

    indexed_count = 0
    skipped_count = 0
    removed_count = 0
    total_chunks = 0

    for source, documents in documents_by_source.items():
        file_hash = str(documents[0].metadata["file_hash"]) if documents else ""
        previous = indexed_files.get(source)

        if not force and previous and previous.file_hash == file_hash:
            skipped_count += 1
            total_chunks += previous.chunk_count
            logger.info("Пропущен без изменений: %s", source)
            continue

        chunk_count = _index_file(
            client,
            source=source,
            documents=documents,
            embeddings=embeddings,
            batch_size=config.rag_embedding_batch_size,
        )
        indexed_count += 1
        total_chunks += chunk_count
        logger.info("Проиндексирован: %s (%s чанков)", source, chunk_count)

    stale_sources = set(indexed_files) - set(documents_by_source)
    for source in sorted(stale_sources):
        _delete_file_index(client, source)
        removed_count += 1
        logger.info("Удалён из индекса: %s", source)

    return ReindexStats(
        scanned_files=len(documents_by_source),
        indexed_files=indexed_count,
        skipped_files=skipped_count,
        removed_files=removed_count,
        total_chunks=total_chunks,
    )
