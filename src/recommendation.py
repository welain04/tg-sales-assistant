from src.catalog import Program, get_programs, match_known_program
from src.session import QUALIFICATION_STEPS

QUESTION_WEIGHTS = (1, 2, 2, 3)

# Совместимость со старым кодом: рекомендации и fallback читают каталог из YAML.
ProgramRecommendation = Program
PROGRAMS = get_programs()


def recommend_from_choices(choice_indices: list[int]) -> tuple[str, str, str]:
    programs = get_programs()
    if len(choice_indices) != len(QUALIFICATION_STEPS):
        fallback = programs[0]
        return fallback.level, fallback.title, fallback.explanation

    weighted_sum = 0.0
    total_weight = 0

    for question_index, option_index in enumerate(choice_indices):
        step = QUALIFICATION_STEPS[question_index]
        option = step.options[option_index]
        weight = QUESTION_WEIGHTS[question_index]
        weighted_sum += option.level_hint * weight
        total_weight += weight

    level_index = round(weighted_sum / total_weight)
    level_index = max(0, min(level_index, len(programs) - 1))
    program = programs[level_index]

    return program.level, program.title, program.explanation


__all__ = [
    "PROGRAMS",
    "ProgramRecommendation",
    "match_known_program",
    "recommend_from_choices",
]
