from dataclasses import dataclass, field
from enum import Enum


class FlowState(str, Enum):
    QUALIFICATION = "qualification"
    QA = "qa"
    AWAITING_QA_CHECK = "awaiting_qa_check"
    COLLECT_NAME = "collect_name"
    COLLECT_EMAIL = "collect_email"
    DONE = "done"


@dataclass(frozen=True)
class QualificationOption:
    short: str
    answer: str
    level_hint: int


@dataclass(frozen=True)
class QualificationStep:
    label: str
    question: str
    options: tuple[QualificationOption, ...]


QUALIFICATION_STEPS: tuple[QualificationStep, ...] = (
    QualificationStep(
        label="Учёт финансов",
        question="1/4. Как вы контролируете личные финансы?",
        options=(
            QualificationOption(
                short="Не слежу за тратами",
                answer="Не слежу — в конце месяца непонятно, куда ушли деньги",
                level_hint=0,
            ),
            QualificationOption(
                short="Записываю от случая к случаю",
                answer="Записываю траты от случая к случаю, без системы",
                level_hint=1,
            ),
            QualificationOption(
                short="Веду учёт каждый месяц",
                answer="Веду учёт в таблице или приложении и вижу итоги каждый месяц",
                level_hint=2,
            ),
        ),
    ),
    QualificationStep(
        label="Накопления и дельта",
        question="2/4. Что ближе к вашей ситуации с отложениями?",
        options=(
            QualificationOption(
                short="К концу месяца пусто",
                answer="К концу месяца почти ничего не остаётся",
                level_hint=0,
            ),
            QualificationOption(
                short="Откладываю нерегулярно",
                answer="Иногда откладываю, но без регулярности",
                level_hint=1,
            ),
            QualificationOption(
                short="Есть сумма, но без системы",
                answer="Каждый месяц остаётся свободная сумма, но она не копится системно",
                level_hint=2,
            ),
            QualificationOption(
                short="Стабильно коплю",
                answer="Стабильно коплю — уже есть сумма на руках или на счёте",
                level_hint=3,
            ),
        ),
    ),
    QualificationStep(
        label="Инвестиционный опыт",
        question="3/4. Какой у вас инвестиционный опыт?",
        options=(
            QualificationOption(
                short="Ничего не пробовал",
                answer="Не инвестировал — только трачу и коплю (или не коплю)",
                level_hint=0,
            ),
            QualificationOption(
                short="Только вклад",
                answer="Пробовал только банковский вклад или накопительный счёт",
                level_hint=1,
            ),
            QualificationOption(
                short="ETF или облигации",
                answer="Покупал ETF или облигации",
                level_hint=2,
            ),
            QualificationOption(
                short="Акции или портфель",
                answer="Покупал акции или собирал портфель из нескольких инструментов",
                level_hint=3,
            ),
        ),
    ),
    QualificationStep(
        label="Приоритетная задача",
        question="4/4. Какая задача для вас сейчас главная?",
        options=(
            QualificationOption(
                short="Разобраться с деньгами",
                answer="Понять, куда уходят деньги, и выстроить базу",
                level_hint=0,
            ),
            QualificationOption(
                short="Бюджет и накопления",
                answer="Настроить бюджет и начать стабильно копить",
                level_hint=1,
            ),
            QualificationOption(
                short="Вложить накопленное",
                answer="Разобраться, как вложить уже накопленное",
                level_hint=2,
            ),
            QualificationOption(
                short="Стратегия капитала",
                answer="Структурировать имеющийся капитал под долгосрочные цели",
                level_hint=3,
            ),
        ),
    ),
)

QUALIFICATION_LABELS = [step.label for step in QUALIFICATION_STEPS]

WELCOME_MESSAGE = (
    "Здравствуйте! Я Алексей, ассистент школы «Финансист».\n\n"
    "Пройдите короткий тест из 4 вопросов — выбирайте ответы кнопками, "
    "я подберу подходящую программу.\n\n"
    "Чтобы получить итоговую рекомендацию, понадобятся ваше имя и email."
)

QA_CHECK_QUESTION = "Остались ли у вас вопросы по программам или обучению?"


@dataclass
class UserSession:
    state: FlowState = FlowState.QUALIFICATION
    qualification_answers: list[str] = field(default_factory=list)
    qualification_choices: list[int] = field(default_factory=list)
    qualification_index: int = 0
    level: str | None = None
    recommended_program: str | None = None
    recommendation_text: str | None = None
    qa_history: list[dict[str, str]] = field(default_factory=list)
    name: str | None = None
    email: str | None = None

    def reset(self) -> None:
        self.state = FlowState.QUALIFICATION
        self.qualification_answers = []
        self.qualification_choices = []
        self.qualification_index = 0
        self.level = None
        self.recommended_program = None
        self.recommendation_text = None
        self.qa_history = []
        self.name = None
        self.email = None

    def current_step(self) -> QualificationStep | None:
        if self.qualification_index < len(QUALIFICATION_STEPS):
            return QUALIFICATION_STEPS[self.qualification_index]
        return None

    def record_qualification_answer(self, answer: str, option_index: int) -> None:
        self.qualification_answers.append(answer)
        self.qualification_choices.append(option_index)
        self.qualification_index += 1

    def qualification_complete(self) -> bool:
        return self.qualification_index >= len(QUALIFICATION_STEPS)
