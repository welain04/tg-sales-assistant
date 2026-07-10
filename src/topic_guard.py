import re
from enum import Enum

OFF_TOPIC_RESPONSE = (
    "Я специализируюсь только на образовательных программах школы «Финансист». "
    "Буду рад помочь с вопросами о наших курсах."
)

INVESTMENT_ADVICE_RESPONSE = (
    "Школа обучает инвестированию, но не предоставляет персональные инвестиционные "
    "рекомендации. Могу рассказать о наших программах обучения."
)

COMPETITOR_RESPONSE = (
    "Не сравниваю программы других школ. Расскажу о курсах «Финансист» — "
    "спросите, например: «какие есть программы?»"
)

DISCOUNT_RESPONSE = (
    "По индивидуальным условиям, скидкам и акциям лучше уточнить у менеджера — "
    "могу передать ваш запрос."
)


class TopicCategory(str, Enum):
    OFF_TOPIC = "off_topic"
    INVESTMENT_ADVICE = "investment_advice"
    COMPETITOR = "competitor"
    DISCOUNT = "discount"


_TOPIC_RESPONSES = {
    TopicCategory.OFF_TOPIC: OFF_TOPIC_RESPONSE,
    TopicCategory.INVESTMENT_ADVICE: INVESTMENT_ADVICE_RESPONSE,
    TopicCategory.COMPETITOR: COMPETITOR_RESPONSE,
    TopicCategory.DISCOUNT: DISCOUNT_RESPONSE,
}

_INVESTMENT_PATTERNS = (
    r"(?:купи|купить|покупать|продай|продать|вложи|вложить|инвестируй|инвестировать)\s+.{0,30}(?:акци|облигац|etf|крипт|валют|сбер|газпром|тинькофф|биткоин)",
    r"(?:что|куда)\s+(?:лучше\s+)?(?:купить|вложить|инвестировать)",
    r"(?:стоит\s+ли|нужно\s+ли)\s+(?:покупать|вкладывать|инвестировать)",
    r"инвестиционн(?:ый|ого|ые)?\s+совет",
    r"прогноз\s+(?:рынка|цен|акци)",
    r"гарантированн.{0,15}доход",
    r"состав(?:ь|ить)\s+(?:мне\s+)?портфел",
    r"какие\s+акции\s+(?:купить|взять)",
)

_COMPETITOR_PATTERNS = (
    r"skillbox",
    r"нетолог",
    r"geekbrains",
    r"skyeng",
    r"сравни\s+.{0,20}(?:школ|курс|программ)",
    r"(?:лучше|хуже)\s+.{0,20}(?:skillbox|нетолог|друг\w+\s+школ)",
    r"чем\s+.{0,20}лучше\s+.{0,20}(?:школ|курс)",
)

_DISCOUNT_PATTERNS = (
    r"скидк",
    r"промокод",
    r"промо[\s\-]?код",
    r"дешевле",
    r"уступ(?:ите|ить)",
    r"индивидуальн.{0,15}услов",
    r"рассрочк",
    r"бонус",
    r"подарок\s+к\s+курс",
)

_OFF_TOPIC_PATTERNS = (
    r"погод",
    r"рецепт",
    r"анекдот",
    r"стихотворен",
    r"политик",
    r"войн[аы]",
    r"футбол",
    r"кино",
    r"сериал",
    r"игр[аыу]\s+(?:в|на)\s+(?!финанс|инвест|деньг)",
    r"напиши\s+код",
    r"реши\s+задач",
    r"переведи\s+на\s+",
)

_TOPIC_CHECKS: tuple[tuple[TopicCategory, tuple[str, ...]], ...] = (
    (TopicCategory.INVESTMENT_ADVICE, _INVESTMENT_PATTERNS),
    (TopicCategory.COMPETITOR, _COMPETITOR_PATTERNS),
    (TopicCategory.DISCOUNT, _DISCOUNT_PATTERNS),
    (TopicCategory.OFF_TOPIC, _OFF_TOPIC_PATTERNS),
)


def classify_topic(text: str) -> TopicCategory | None:
    normalized = text.strip().lower().replace("ё", "е")
    if not normalized:
        return None

    for category, patterns in _TOPIC_CHECKS:
        if any(re.search(pattern, normalized) for pattern in patterns):
            return category
    return None


def check_topic(text: str) -> tuple[str, bool] | None:
    category = classify_topic(text)
    if category is None:
        return None
    needs_escalation = category == TopicCategory.DISCOUNT
    return _TOPIC_RESPONSES[category], needs_escalation
