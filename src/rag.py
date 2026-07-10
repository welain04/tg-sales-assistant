import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KnowledgeChunk:
    source: str
    text: str


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
        source = str(path.relative_to(knowledge_dir))
        chunks.extend(_split_into_chunks(text, source))

    return chunks


def _tokenize(text: str) -> set[str]:
    return {word for word in re.findall(r"[а-яёa-z0-9]+", text.lower()) if len(word) > 2}


def _score_chunk(query: str, chunk: KnowledgeChunk) -> int:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0
    chunk_tokens = _tokenize(chunk.text)
    return len(query_tokens & chunk_tokens)


def best_chunk_score(query: str, chunks: list[KnowledgeChunk]) -> int:
    if not chunks:
        return 0
    return max(_score_chunk(query, chunk) for chunk in chunks)


def retrieve_context(
    query: str,
    chunks: list[KnowledgeChunk],
    max_chunks: int = 5,
) -> str:
    if not chunks:
        return "Контекст не найден. База знаний пуста."

    ranked = sorted(
        chunks,
        key=lambda chunk: (_score_chunk(query, chunk), len(chunk.text)),
        reverse=True,
    )

    top_score = best_chunk_score(query, chunks)
    selected = ranked[:max_chunks] if top_score > 0 else ranked

    parts = []
    for chunk in selected:
        parts.append(f"[{chunk.source}]\n{chunk.text}")

    return "\n\n---\n\n".join(parts)
