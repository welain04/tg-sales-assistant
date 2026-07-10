import re

from src.rag import KnowledgeChunk, _score_chunk
from src.recommendation import PROGRAMS

_CATALOG_PATTERNS = (
    r"какие\s+(?:есть\s+)?программ",
    r"какие\s+(?:есть\s+)?курс",
    r"что\s+(?:у\s+вас\s+)?(?:есть|предлагаете)",
    r"список\s+программ",
    r"список\s+курс",
    r"все\s+программ",
    r"все\s+курс",
    r"какие\s+продукт",
    r"расскаж(?:и|ите)\s+о\s+программ",
    r"расскаж(?:и|ите)\s+о\s+курс",
)

_PRICE_PATTERNS = (
    r"сколько\s+стоит",
    r"\bцена\b",
    r"стоимость",
    r"ценник",
    r"почём",
    r"по\s+чём",
)

_LEVEL_PATTERNS = (
    r"какой\s+уровень",
    r"какие\s+уровн",
    r"для\s+новичк",
    r"для\s+начинающ",
)


def _normalize(text: str) -> str:
    return text.strip().lower().replace("ё", "е")


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _catalog_answer() -> str:
    lines = ["В школе «Финансист» 4 программы:"]
    for index, program in enumerate(PROGRAMS, start=1):
        lines.append(
            f"{index}. {program.program} — {program.price}. {program.summary}."
        )
    return "\n".join(lines)


def _price_answer(query: str) -> str | None:
    normalized = _normalize(query)
    for program in PROGRAMS:
        if _program_mentioned(normalized, program):
            return f"«{program.program}» стоит {program.price}."
    if _matches_any(normalized, _PRICE_PATTERNS):
        return "Стоимость программ:\n" + "\n".join(
            f"• {program.program} — {program.price}" for program in PROGRAMS
        )
    return None


def _program_mentioned(query: str, program) -> bool:
    markers = (
        _normalize(program.program),
        _normalize(program.level),
    )
    for marker in markers:
        compact = re.sub(r"[«»\"'']", "", marker)
        if compact and compact in query:
            return True
        for part in re.findall(r"[а-яa-z0-9]{4,}", compact):
            if part in query:
                return True
    return False


def _find_program(query: str):
    normalized = _normalize(query)
    for program in PROGRAMS:
        if _program_mentioned(normalized, program):
            return program
    return None


def _program_answer(program) -> str:
    return (
        f"«{program.program}» — {program.price}. "
        f"Уровень: {program.level}. {program.summary}."
    )


def _chunk_answer(chunk: KnowledgeChunk) -> str:
    fields = {
        "Продукт": _extract_field(chunk.text, "Продукт"),
        "Цена": _extract_field(chunk.text, "Цена"),
        "Для кого": _extract_field(chunk.text, "Для кого"),
        "Результат": _extract_field(chunk.text, "Тезисно, какие результаты даст продукт"),
    }
    product = fields["Продукт"] or "Программа"
    price = fields["Цена"] or ""
    audience = fields["Для кого"] or ""
    result = fields["Результат"] or ""

    parts = [product]
    if price:
        parts.append(price)
    if audience:
        parts.append(audience)
    if result:
        parts.append(result)
    return ". ".join(parts) + "."


def _extract_field(text: str, label: str) -> str | None:
    match = re.search(rf"{re.escape(label)}:\s*(.+)", text)
    if not match:
        return None
    return match.group(1).strip().strip('"')


def answer_from_knowledge(query: str, chunks: list[KnowledgeChunk]) -> str | None:
    normalized = _normalize(query)

    if _matches_any(normalized, _CATALOG_PATTERNS):
        return _catalog_answer()

    price_answer = _price_answer(query)
    if price_answer:
        return price_answer

    if _matches_any(normalized, _LEVEL_PATTERNS):
        return "Уровни программ:\n" + "\n".join(
            f"• {program.level} — {program.program}" for program in PROGRAMS
        )

    program = _find_program(query)
    if program:
        return _program_answer(program)

    if chunks:
        ranked = sorted(
            chunks,
            key=lambda chunk: (_score_chunk(query, chunk), len(chunk.text)),
            reverse=True,
        )
        if _score_chunk(query, ranked[0]) > 0:
            return _chunk_answer(ranked[0])

    return None


def generic_qa_fallback() -> str:
    return (
        "Могу рассказать о программах школы, их стоимости и содержании. "
        "Например, спросите: «какие есть программы?»"
    )
