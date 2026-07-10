import re

NO_MORE_QUESTIONS_PATTERNS = (
    r"^нет[.!?,]?\s*$",
    r"^не[тt][.!?,]?\s*$",
    r"вопросов\s+нет",
    r"нет\s+вопрос",
    r"не\s+остал",
    r"больше\s+нет",
    r"вс[её]\s+понят",
    r"вс[её]\s+ясн",
    r"ничего",
    r"^ок[.!]?$",
    r"^готов[аоы]?[.!]?$",
)

EMAIL_PATTERN = re.compile(
    r"[a-z0-9][a-z0-9._%+\-]*@[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?)+",
    re.IGNORECASE,
)

NAME_RE = re.compile(r"^[\wА-Яа-яЁё\- ]{2,60}$", re.UNICODE)

# Похожие кириллические символы → латиница (частая ошибка при вводе)
_CYRILLIC_LOOKALIKES = str.maketrans(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ",
    "abvgdeejzijklmnoprstufhzcss_y_euaABVGDEEJZIJKLMNOPRSTUFHZCSS_Y_EUA",
)


def has_no_more_questions(text: str) -> bool:
    normalized = text.strip().lower()
    return any(re.search(pattern, normalized) for pattern in NO_MORE_QUESTIONS_PATTERNS)


def _normalize_email_input(text: str) -> str:
    value = text.strip().lower().replace("＠", "@")
    value = value.translate(_CYRILLIC_LOOKALIKES)
    value = value.rstrip(".,;:!?")

    for prefix in ("email:", "e-mail:", "почта:", "mail:", "мой email", "моя почта"):
        if value.startswith(prefix):
            value = value[len(prefix):].strip(" :")

    return value


def parse_email(text: str) -> str | None:
    normalized = _normalize_email_input(text)

    if EMAIL_PATTERN.fullmatch(normalized):
        return normalized

    match = EMAIL_PATTERN.search(normalized)
    if match:
        return match.group(0).lower()

    return None


def is_valid_email(text: str) -> bool:
    return parse_email(text) is not None


def is_valid_name(text: str) -> bool:
    cleaned = text.strip()
    return bool(NAME_RE.match(cleaned)) and len(cleaned.split()) >= 1
