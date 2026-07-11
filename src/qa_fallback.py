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

_REFUND_PATTERNS = (
    r"вернуть\s+деньг",
    r"вернуть\s+оплат",
    r"возврат",
    r"вернут\s+деньг",
    r"можно\s+ли\s+вернуть",
)

_PACKAGE_PATTERNS = (
    r"пакет",
    r"нескольк\w+\s+курс",
)

_INSTALLMENT_PATTERNS = (
    r"рассрочк",
)

_RECOMMENDATION_PATTERNS = (
    r"какой\s+курс\s+выбрать",
    r"что\s+выбрать",
    r"с\s+чего\s+начать",
    r"какой\s+курс\s+подойд",
    r"какой\s+курс\s+лучше",
)

# Слишком общие слова — не считаем упоминанием конкретной программы.
_PROGRAM_STOPWORDS = frozenset({
    "курс", "курса", "курсов", "курсе", "онлайн", "стартовый", "стартового",
    "личный", "личного", "первые", "первых", "практикум", "персональная",
    "стратегия", "база", "базы", "нуля", "нуль", "дельта", "дельты", "бюджет",
    "бюджета", "капитал", "капитала", "цели", "целей", "финансовая", "финансовой",
    "финансах", "финансов", "инвестор", "инвестора", "новичок", "новичку",
    "новичка", "программ", "программа", "программы", "школа", "школы",
    "обучение", "обучения", "стоит", "цена", "рублей",
})


def _normalize(text: str) -> str:
    return text.strip().lower().replace("ё", "е")


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _catalog_answer() -> str:
    lines = ["В школе «Финансист» 4 программы:"]
    for index, program in enumerate(PROGRAMS, start=1):
        lines.append(
            f"{index}. {program.title} — {program.price}. {program.summary}."
        )
    return "\n".join(lines)


def _price_answer(query: str) -> str | None:
    normalized = _normalize(query)
    for program in PROGRAMS:
        if _program_mentioned(normalized, program):
            return f"«{program.title}» стоит {program.price}."
    if _matches_any(normalized, _PRICE_PATTERNS):
        return "Стоимость программ:\n" + "\n".join(
            f"• {program.title} — {program.price}" for program in PROGRAMS
        )
    return None


def _program_mentioned(query: str, program) -> bool:
    markers = (
        _normalize(program.title),
        _normalize(program.level),
    )
    for marker in markers:
        compact = re.sub(r"[«»\"'']", "", marker)
        if len(compact) >= 12 and compact in query:
            return True
        for part in re.findall(r"[а-яa-z0-9]{5,}", compact):
            if part in _PROGRAM_STOPWORDS:
                continue
            if re.search(rf"(?<![а-яa-z0-9]){re.escape(part)}", query):
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
        f"«{program.title}» — {program.price}. "
        f"Уровень: {program.level}. {program.summary}."
    )


def _faq_answer(chunk: KnowledgeChunk) -> str | None:
    answer = _extract_field(chunk.text, "Ответ")
    if answer:
        return answer
    return None


def _find_faq_answer(query: str, chunks: list[KnowledgeChunk]) -> str | None:
    normalized = _normalize(query)
    best_score = 0
    best_answer: str | None = None

    for chunk in chunks:
        question = _extract_field(chunk.text, "Вопрос")
        answer = _extract_field(chunk.text, "Ответ")
        if not question or not answer:
            continue

        question_normalized = _normalize(question)
        score = _score_chunk(query, chunk)
        if normalized in question_normalized or question_normalized in normalized:
            score += 3
        if score > best_score:
            best_score = score
            best_answer = answer

    return best_answer if best_score > 0 else None


def _chunk_answer(chunk: KnowledgeChunk) -> str | None:
    faq_answer = _faq_answer(chunk)
    if faq_answer:
        return faq_answer

    fields = {
        "Продукт": _extract_field(chunk.text, "Продукт"),
        "Цена": _extract_field(chunk.text, "Цена"),
        "Для кого": _extract_field(chunk.text, "Для кого"),
        "Результат": _extract_field(chunk.text, "Тезисно, какие результаты даст продукт"),
    }
    product = fields["Продукт"]
    price = fields["Цена"] or ""
    audience = fields["Для кого"] or ""
    result = fields["Результат"] or ""

    if not product and not price and not audience and not result:
        return None

    parts = [product or "Программа"]
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


def _installment_answer(chunks: list[KnowledgeChunk]) -> str | None:
    for chunk in chunks:
        for line in chunk.text.splitlines():
            normalized_line = _normalize(line)
            if normalized_line.startswith("рассрочка:") or (
                "рассрочк" in normalized_line and "10000" in normalized_line
            ):
                return line.strip()
    return None


_LOCAL_FALLBACK_PATTERNS = (
    *_CATALOG_PATTERNS,
    *_PRICE_PATTERNS,
    *_LEVEL_PATTERNS,
    *_REFUND_PATTERNS,
    *_INSTALLMENT_PATTERNS,
    *_PACKAGE_PATTERNS,
    *_RECOMMENDATION_PATTERNS,
)

_DETERMINISTIC_LOCAL_PATTERNS = (
    *_CATALOG_PATTERNS,
    *_LEVEL_PATTERNS,
)

_STRUCTURED_FAQ_PATTERNS = (
    *_REFUND_PATTERNS,
    *_INSTALLMENT_PATTERNS,
    *_PACKAGE_PATTERNS,
    *_RECOMMENDATION_PATTERNS,
)

UNKNOWN_QA_MESSAGE = (
    "В базе знаний школы нет точного ответа на этот вопрос. "
    "Могу рассказать о программах, стоимости, формате обучения и возврате — "
    "или передать вопрос менеджеру."
)


def unknown_qa_fallback() -> str:
    return UNKNOWN_QA_MESSAGE


def generic_qa_fallback() -> str:
    return unknown_qa_fallback()


def should_use_llm(
    *,
    top_score: float,
    relevance_threshold: float,
    rag_context: str,
) -> bool:
    from src.rag import is_usable_rag_context

    return top_score >= relevance_threshold and is_usable_rag_context(rag_context)


def _answer_structured_faq(
    query: str,
    *chunk_lists: list[KnowledgeChunk],
) -> str | None:
    normalized = _normalize(query)

    if _matches_any(normalized, _REFUND_PATTERNS):
        for chunks in chunk_lists:
            refund_answer = _find_faq_answer(
                "можно ли вернуть деньги если курс не подошел",
                chunks,
            )
            if refund_answer:
                return refund_answer

    if _matches_any(normalized, _INSTALLMENT_PATTERNS):
        for chunks in chunk_lists:
            installment_answer = _installment_answer(chunks)
            if installment_answer:
                return installment_answer

    if (
        _matches_any(normalized, _PACKAGE_PATTERNS)
        or _matches_any(normalized, _RECOMMENDATION_PATTERNS)
    ):
        for chunks in chunk_lists:
            faq_answer = _find_faq_answer(query, chunks)
            if faq_answer:
                return faq_answer

    return None


def answer_from_search(
    query: str,
    search_chunks: list[KnowledgeChunk],
    local_chunks: list[KnowledgeChunk],
    *,
    top_score: float = 0.0,
    relevance_threshold: float = 0.55,
) -> tuple[str | None, str | None]:
    """Сначала отвечает по результатам поиска, затем — по полной локальной базе."""
    normalized = _normalize(query)

    if _matches_any(normalized, _STRUCTURED_FAQ_PATTERNS):
        structured_answer = _answer_structured_faq(query, search_chunks, local_chunks)
        if structured_answer:
            found_in_search = _answer_structured_faq(query, search_chunks) is not None
            return structured_answer, "search_rule" if found_in_search else "local_rule"

    if search_chunks:
        answer = answer_from_knowledge(query, search_chunks)
        if answer:
            normalized = _normalize(query)
            if top_score >= relevance_threshold or _matches_any(
                normalized,
                _DETERMINISTIC_LOCAL_PATTERNS + _STRUCTURED_FAQ_PATTERNS,
            ):
                return answer, "search_rule"

    normalized = _normalize(query)
    if _matches_any(normalized, _DETERMINISTIC_LOCAL_PATTERNS):
        answer = answer_from_knowledge(query, local_chunks)
        if answer:
            return answer, "local_deterministic"

    if _matches_any(normalized, _PRICE_PATTERNS) and (
        _find_program(query) is not None or top_score >= relevance_threshold
    ):
        answer = answer_from_knowledge(query, local_chunks)
        if answer:
            return answer, "local_deterministic"

    if top_score >= relevance_threshold and _matches_any(normalized, _STRUCTURED_FAQ_PATTERNS):
        answer = answer_from_knowledge(query, local_chunks)
        if answer:
            return answer, "local_rule"

    return None, None


def answer_from_knowledge(query: str, chunks: list[KnowledgeChunk]) -> str | None:
    normalized = _normalize(query)

    if _matches_any(normalized, _CATALOG_PATTERNS):
        return _catalog_answer()

    if _matches_any(normalized, _REFUND_PATTERNS):
        refund_answer = _find_faq_answer(
            "можно ли вернуть деньги если курс не подошел",
            chunks,
        )
        if refund_answer:
            return refund_answer

    if _matches_any(normalized, _INSTALLMENT_PATTERNS):
        installment_answer = _installment_answer(chunks)
        if installment_answer:
            return installment_answer

    if (
        _matches_any(normalized, _PACKAGE_PATTERNS)
        or _matches_any(normalized, _RECOMMENDATION_PATTERNS)
    ):
        faq_answer = _find_faq_answer(query, chunks)
        if faq_answer:
            return faq_answer

    faq_answer = _find_faq_answer(query, chunks)
    if faq_answer:
        return faq_answer

    price_answer = _price_answer(query)
    if price_answer:
        return price_answer

    if _matches_any(normalized, _LEVEL_PATTERNS):
        return "Уровни программ:\n" + "\n".join(
            f"• {program.level} — {program.title}" for program in PROGRAMS
        )

    program = _find_program(query)
    if program:
        return _program_answer(program)

    if chunks:
        if _matches_any(normalized, _STRUCTURED_FAQ_PATTERNS):
            return None

        ranked = sorted(
            chunks,
            key=lambda chunk: (_score_chunk(query, chunk), len(chunk.text)),
            reverse=True,
        )
        if _score_chunk(query, ranked[0]) > 0:
            chunk_answer = _chunk_answer(ranked[0])
            if chunk_answer:
                return chunk_answer

    return None
