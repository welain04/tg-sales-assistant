import re
from dataclasses import dataclass

from src.session import QUALIFICATION_STEPS

QUESTION_WEIGHTS = (1, 2, 2, 3)


@dataclass(frozen=True)
class ProgramRecommendation:
    level: str
    program: str
    price: str
    summary: str
    explanation: str


PROGRAMS: tuple[ProgramRecommendation, ...] = (
    ProgramRecommendation(
        level="Новичок в финансах",
        program="Стартовый онлайн-курс «Финансовая база с нуля»",
        price="3000 ₽",
        summary="Учёт доходов и расходов, основа финансовой подушки",
        explanation=(
            "Сейчас важнее всего навести порядок в деньгах: понять доходы и расходы "
            "и заложить основу финансовой подушки."
        ),
    ),
    ProgramRecommendation(
        level="Финансовый базовый уровень",
        program="Практикум «Личный бюджет и первая дельта»",
        price="5000 ₽",
        summary="Рабочий бюджет и первая стабильная дельта",
        explanation=(
            "У вас уже есть базовое понимание финансов, но пока не выстроена стабильная "
            "привычка копить — практикум поможет настроить бюджет и первую дельту."
        ),
    ),
    ProgramRecommendation(
        level="Растущий инвестор",
        program="Курс «Первые инвестиции: от дельты к капиталу»",
        price="10000 ₽",
        summary="Базовые инструменты и первый портфель",
        explanation=(
            "У вас уже есть накопления и интерес к инвестициям — курс поможет освоить "
            "базовые инструменты и собрать первый портфель."
        ),
    ),
    ProgramRecommendation(
        level="Осознанный инвестор с капиталом",
        program="Персональная стратегия «Капитал под цели»",
        price="15000 ₽",
        summary="Стратегия распределения капитала под цели",
        explanation=(
            "У вас уже есть капитал и опыт — сейчас важно структурировать вложения "
            "под долгосрочные цели и выстроить понятную стратегию."
        ),
    ),
)


def _normalize_program_name(name: str) -> str:
    normalized = name.strip().lower().replace("ё", "е")
    return re.sub(r"[«»\"'']", "", normalized)


def match_known_program(program_name: str) -> ProgramRecommendation | None:
    normalized = _normalize_program_name(program_name)
    if not normalized:
        return None

    for program in PROGRAMS:
        candidates = (
            _normalize_program_name(program.program),
            _normalize_program_name(program.level),
        )
        if any(
            normalized == candidate or normalized in candidate or candidate in normalized
            for candidate in candidates
            if candidate
        ):
            return program
    return None


def recommend_from_choices(choice_indices: list[int]) -> tuple[str, str, str]:
    if len(choice_indices) != len(QUALIFICATION_STEPS):
        fallback = PROGRAMS[0]
        return fallback.level, fallback.program, fallback.explanation

    weighted_sum = 0.0
    total_weight = 0

    for question_index, option_index in enumerate(choice_indices):
        step = QUALIFICATION_STEPS[question_index]
        option = step.options[option_index]
        weight = QUESTION_WEIGHTS[question_index]
        weighted_sum += option.level_hint * weight
        total_weight += weight

    level_index = round(weighted_sum / total_weight)
    level_index = max(0, min(level_index, len(PROGRAMS) - 1))
    program = PROGRAMS[level_index]

    return program.level, program.program, program.explanation
