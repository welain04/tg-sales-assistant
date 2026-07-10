import re

MANAGER_REQUEST_PATTERNS = (
    r"менеджер",
    r"оператор",
    r"человек",
    r"живой\s+человек",
    r"свяж(?:ите|ись|исьте|итесь)",
    r"связать",
    r"связь\s+с",
    r"передай(?:те)?",
    r"передать",
    r"перезвон",
    r"позвон",
    r"консультант",
    r"специалист",
    r"сотрудник",
    r"поговорить\s+с",
    r"хочу\s+поговорить",
    r"нужен\s+человек",
    r"нужен\s+менеджер",
    r"помогите\s+связать",
    r"хочу\s+менеджера",
    r"свяжите\s+меня",
)

ESCALATION_ANSWER_PATTERNS = (
    r"информаци\w*\s+недостаточно",
    r"обратитесь\s+к\s+менеджеру",
    r"уточните\s+у\s+менеджера",
    r"не\s+могу\s+ответить",
    r"нет\s+информации",
    r"в\s+контексте\s+нет",
    r"менеджер\s+может",
    r"менеджер\s+сообщит",
    r"менеджер\s+уточнит",
    r"менеджер\s+свяжется",
)


def wants_manager(text: str) -> bool:
    normalized = text.strip().lower()
    return any(re.search(pattern, normalized) for pattern in MANAGER_REQUEST_PATTERNS)


def answer_needs_escalation(answer: str) -> bool:
    normalized = answer.strip().lower()
    return any(re.search(pattern, normalized) for pattern in ESCALATION_ANSWER_PATTERNS)
