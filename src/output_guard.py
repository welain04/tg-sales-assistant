import re

from src.qa_fallback import UNKNOWN_QA_MESSAGE
from src.recommendation import PROGRAMS

_INVESTMENT_OUTPUT_PATTERNS = (
    r"(?:рекомендую|советую)\s+(?:купить|вложить|инвестировать|продать)",
    r"(?:покупайте|покупай|продавайте|продавай|вкладывайте|вкладывай)\s+",
    r"гарантированн.{0,15}(?:доход|прибыл)",
    r"прогноз\s+(?:рынка|цен|акци)",
    r"состав(?:ь|ить)\s+(?:вам\s+)?портфел",
)

_INTERNAL_LEAK_PATTERNS = (
    r"системн(?:ый|ого)\s+промпт",
    r"api[\s\-]?ключ",
    r"webhook",
    r"\.env",
    r"исходн(?:ый|ого)\s+код",
)

_SAFE_FALLBACK = UNKNOWN_QA_MESSAGE

_ADMISSION_PATTERNS = (
    r"нет\s+информации",
    r"информаци\w*\s+недостаточно",
    r"не\s+могу\s+ответить",
    r"в\s+контексте\s+нет",
    r"не\s+нашел",
    r"не\s+нашёл",
    r"не\s+знаю",
    r"нет\s+точного\s+ответа",
    r"передам\s+вопрос\s+менеджер",
    r"передать\s+вопрос\s+менеджер",
)

_KNOWN_PRICES = {program.price for program in PROGRAMS}
_PRICE_RE = re.compile(r"\d[\d\s]*\s*₽")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")


def _normalize(text: str) -> str:
    return text.strip().lower().replace("ё", "е")


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    normalized = _normalize(text)
    return any(re.search(pattern, normalized) for pattern in patterns)


def _extract_prices(text: str) -> set[str]:
    return {match.group(0).strip() for match in _PRICE_RE.finditer(text)}


def _admits_unknown(answer: str) -> bool:
    return _matches_any(answer, _ADMISSION_PATTERNS)


def _has_unknown_program(answer: str, rag_context: str) -> bool:
    if _admits_unknown(answer):
        return False

    normalized_answer = _normalize(answer)
    normalized_context = _normalize(rag_context)
    for program in PROGRAMS:
        compact = re.sub(r"[«»\"'']", "", _normalize(program.program))
        if len(compact) >= 12 and compact in normalized_answer and compact not in normalized_context:
            return True
    return False


def _has_unknown_price(answer: str, rag_context: str) -> bool:
    if _admits_unknown(answer):
        return False

    answer_prices = _extract_prices(answer)
    if not answer_prices:
        return False

    allowed = set(_KNOWN_PRICES)
    allowed.update(_extract_prices(rag_context))

    return any(price not in allowed for price in answer_prices)


def trim_answer_length(answer: str, max_sentences: int = 3) -> str:
    text = answer.strip()
    if not text:
        return text

    sentences = [part.strip() for part in _SENTENCE_SPLIT_RE.split(text) if part.strip()]
    if len(sentences) <= max_sentences:
        return text

    return " ".join(sentences[:max_sentences])


def sanitize_llm_answer(answer: str, rag_context: str) -> tuple[str, bool]:
    text = answer.strip()
    if not text:
        return _SAFE_FALLBACK, True

    if _matches_any(text, _INTERNAL_LEAK_PATTERNS):
        return _SAFE_FALLBACK, True

    if _matches_any(text, _INVESTMENT_OUTPUT_PATTERNS):
        return (
            "Школа обучает инвестированию, но не предоставляет персональные "
            "инвестиционные рекомендации. Могу рассказать о наших программах обучения.",
            False,
        )

    if _has_unknown_program(text, rag_context):
        return _SAFE_FALLBACK, True

    if _has_unknown_price(text, rag_context):
        return _SAFE_FALLBACK, True

    return trim_answer_length(text), False
