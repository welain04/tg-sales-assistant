import re

INJECTION_SAFE_RESPONSE = (
    "Я консультирую только по программам обучения школы «Финансист». "
    "Чем могу помочь с выбором курса?"
)

_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE | re.UNICODE)
    for pattern in (
        # English jailbreak patterns
        r"ignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+instructions",
        r"disregard\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+instructions",
        r"forget\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+instructions",
        r"override\s+(?:the\s+)?system",
        r"system\s+override",
        r"developer\s+mode",
        r"debug\s+mode",
        r"\bdan\b",
        r"jailbreak",
        r"act\s+as\s+(?:a\s+)?",
        r"you\s+are\s+now\s+",
        r"pretend\s+(?:you\s+are|to\s+be)\s+",
        r"(?:show|print|reveal|output|display|repeat|dump)\s+(?:me\s+)?(?:your\s+)?(?:system\s+)?(?:prompt|instructions)",
        r"what\s+are\s+your\s+(?:system\s+)?instructions",
        r"repeat\s+(?:the\s+)?(?:system\s+)?(?:prompt|instructions)",
        # Russian jailbreak patterns
        r"забудь\s+(?:все\s+)?(?:предыдущ|прошл|сво).{0,20}инструкц",
        r"игнорируй\s+(?:все\s+)?(?:предыдущ|прошл|сво).{0,20}инструкц",
        r"отмени\s+(?:все\s+)?(?:предыдущ|прошл|сво).{0,20}инструкц",
        r"(?:покажи|выведи|раскрой|напиши|повтори|открой|скинь|дай)\s+.{0,30}(?:системн|скрыт|внутренн|полн).{0,20}(?:промпт|инструкц|контекст|документ)",
        r"(?:покажи|выведи|раскрой)\s+(?:весь\s+)?(?:промпт|контекст|инструкц|документ)",
        r"системн(?:ый|ого|ые)?\s+промпт",
        r"режим\s+(?:разработчик|отладк|админ|бога|без\s+ограничен)",
        r"теперь\s+ты\s+(?:не\s+)?(?:ассистент|бот|ai|ии|нейросет|модел|разработчик|админ|хакер)",
        r"представь\s*,?\s*что\s+ты\s+",
        r"(?:измени|поменяй|обнови|перепиши)\s+.{0,20}(?:промпт|код|настройк|поведени|роль|инструкц)",
        r"(?:доступ|доступа)\s+к\s+(?:данн|клиент|баз|таблиц|лог)",
        r"(?:исходн(?:ый|ого)?\s+код|архитектур(?:а|у)\s+бота|внутренн(?:ее|ие)\s+устройств)",
        r"(?:api[\s\-]?ключ|токен\s+(?:бота|telegram|groq)|webhook[\s\-]?url)",
        r"(?:\.env|rag[\s\-]?контекст|эмбеддинг)",
        r"(?:ignore|system|developer)\s+mode",
    )
)


def is_prompt_injection(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    return any(pattern.search(normalized) for pattern in _INJECTION_PATTERNS)
