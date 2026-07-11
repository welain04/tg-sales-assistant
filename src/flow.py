import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from src.config import settings
from src.injection_guard import INJECTION_SAFE_RESPONSE, is_prompt_injection
from src.intents import answer_needs_escalation, wants_manager
from src.llm import AssistantLLM
from src.notifications import notify_manager_escalation, notify_manager_lead
from src.output_guard import sanitize_llm_answer
from src.qa_fallback import answer_from_search, should_use_llm, unknown_qa_fallback
from src.rag import KnowledgeChunk, KnowledgeRetriever, format_retrieval_log, format_retrieved_context
from src.recommendation import match_known_program, recommend_from_choices
from src.session import FlowState, QA_CHECK_QUESTION, UserSession, WELCOME_MESSAGE
from src.sheets import submit_lead
from src.topic_guard import check_topic
from src.validators import has_no_more_questions, is_valid_name, parse_email

logger = logging.getLogger(__name__)

QUIZ_CALLBACK_PREFIX = "quiz"

MANAGER_CONFIRMED_MESSAGE = "Передал ваш запрос менеджеру — он свяжется с вами."
MANAGER_FAILED_MESSAGE = (
    "Не удалось отправить уведомление менеджеру. "
    "Напишите нам напрямую или попробуйте позже."
)


def get_session(context: ContextTypes.DEFAULT_TYPE) -> UserSession:
    if "session" not in context.user_data:
        context.user_data["session"] = UserSession()
    return context.user_data["session"]


def reset_session(context: ContextTypes.DEFAULT_TYPE) -> UserSession:
    session = get_session(context)
    session.reset()
    return session


def _build_qualification_keyboard(question_index: int) -> InlineKeyboardMarkup:
    from src.session import QUALIFICATION_STEPS

    step = QUALIFICATION_STEPS[question_index]
    rows = [
        [
            InlineKeyboardButton(
                option.short,
                callback_data=f"{QUIZ_CALLBACK_PREFIX}:{question_index}:{option_index}",
            )
        ]
        for option_index, option in enumerate(step.options)
    ]
    return InlineKeyboardMarkup(rows)


async def _safe_typing(update: Update) -> None:
    chat = update.effective_chat
    if not chat:
        return
    try:
        await chat.send_action(ChatAction.TYPING)
    except Exception:
        logger.warning("sendChatAction failed", exc_info=True)


async def _send_qualification_question(
    update: Update,
    session: UserSession,
    *,
    prefix: str | None = None,
) -> None:
    step = session.current_step()
    if not step:
        return

    text_parts = []
    if prefix:
        text_parts.append(prefix)
    text_parts.append(step.question)

    chat = update.effective_chat
    if not chat:
        return

    await chat.send_message(
        "\n\n".join(text_parts),
        reply_markup=_build_qualification_keyboard(session.qualification_index),
    )


async def _reply_if_injection(
    update: Update,
    session: UserSession,
    user_text: str,
) -> bool:
    if not is_prompt_injection(user_text):
        return False

    message = INJECTION_SAFE_RESPONSE
    if session.state == FlowState.QUALIFICATION:
        message = (
            f"{INJECTION_SAFE_RESPONSE}\n\n"
            "Выберите ответ кнопкой под вопросом."
        )
    elif session.state in (FlowState.QA, FlowState.AWAITING_QA_CHECK):
        message = f"{INJECTION_SAFE_RESPONSE}\n\n{QA_CHECK_QUESTION}"
    elif session.state == FlowState.COLLECT_NAME:
        message = f"{INJECTION_SAFE_RESPONSE}\n\nНапишите ваше имя."
    elif session.state == FlowState.COLLECT_EMAIL:
        message = f"{INJECTION_SAFE_RESPONSE}\n\nУкажите ваш email."

    await update.message.reply_text(message)
    return True


async def _reply_if_off_topic(
    update: Update,
    session: UserSession,
    user_text: str,
    *,
    context: ContextTypes.DEFAULT_TYPE | None = None,
    user_message: str | None = None,
) -> bool:
    if session.state not in (FlowState.QA, FlowState.AWAITING_QA_CHECK):
        return False

    topic_result = check_topic(user_text)
    if topic_result is None:
        return False

    response, needs_escalation = topic_result
    if needs_escalation and context is not None:
        await _handle_manager_request(
            update,
            context,
            "Клиент интересуется индивидуальными условиями",
            user_message=user_message or user_text,
        )

    await update.message.reply_text(f"{response}\n\n{QA_CHECK_QUESTION}")
    session.state = FlowState.AWAITING_QA_CHECK
    return True


async def start_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = reset_session(context)
    context.user_data["flow_initialized"] = True
    await _send_qualification_question(update, session, prefix=WELCOME_MESSAGE)


async def handle_flow_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    if not context.user_data.get("flow_initialized"):
        context.user_data["flow_initialized"] = True

    await _handle_qualification_callback(update, context)


async def _handle_qualification_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    session = get_session(context)
    if session.state != FlowState.QUALIFICATION:
        return

    parts = query.data.split(":")
    if len(parts) != 3 or parts[0] != QUIZ_CALLBACK_PREFIX:
        return

    try:
        question_index = int(parts[1])
        option_index = int(parts[2])
    except ValueError:
        return

    if question_index != session.qualification_index:
        return

    from src.session import QUALIFICATION_STEPS

    step = QUALIFICATION_STEPS[question_index]
    if option_index < 0 or option_index >= len(step.options):
        return

    selected = step.options[option_index]
    session.record_qualification_answer(selected.answer, option_index)

    if query.message:
        await query.message.edit_text(
            f"{step.question}\n\n✓ {selected.short}",
            reply_markup=None,
        )

    if not session.qualification_complete():
        await _send_qualification_question(update, session)
        return

    llm: AssistantLLM = context.application.bot_data["llm"]
    retriever: KnowledgeRetriever = context.application.bot_data["retriever"]
    await _finish_qualification(update, context, session, llm, retriever)


async def handle_flow_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    if not context.user_data.get("flow_initialized"):
        await start_flow(update, context)
        return

    user_text = update.message.text.strip()
    if not user_text:
        return

    session = get_session(context)
    if await _reply_if_injection(update, session, user_text):
        return

    llm: AssistantLLM = context.application.bot_data["llm"]
    retriever: KnowledgeRetriever = context.application.bot_data["retriever"]
    knowledge = retriever.local_chunks

    await _safe_typing(update)

    if session.state == FlowState.QUALIFICATION:
        await _handle_qualification_text(update, context, session, user_text)
    elif session.state == FlowState.QA:
        await _handle_qa(update, context, session, llm, retriever, knowledge, user_text)
    elif session.state == FlowState.AWAITING_QA_CHECK:
        await _handle_qa_check(update, context, session, llm, retriever, knowledge, user_text)
    elif session.state == FlowState.COLLECT_NAME:
        await _handle_collect_name(update, session, user_text)
    elif session.state == FlowState.COLLECT_EMAIL:
        await _handle_collect_email(update, context, session, user_text)
    elif session.state == FlowState.DONE:
        await update.message.reply_text(
            "Ваша заявка уже принята. Чтобы начать заново — /reset."
        )


async def _handle_manager_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    reason: str,
    *,
    user_message: str = "Запрос связи с менеджером",
) -> None:
    session = get_session(context)
    notified = await notify_manager_escalation(
        bot=context.bot,
        user=update.effective_user,
        session=session,
        question=user_message,
        reason=reason,
    )

    message = MANAGER_CONFIRMED_MESSAGE if notified else MANAGER_FAILED_MESSAGE
    chat = update.effective_chat
    if not chat:
        return

    if session.state == FlowState.QUALIFICATION:
        await chat.send_message(f"{message} Продолжите тест кнопками или напишите /reset.")
        return

    if session.state == FlowState.AWAITING_QA_CHECK:
        await chat.send_message(f"{message}\n\n{QA_CHECK_QUESTION}")
        return

    await chat.send_message(message)


async def _handle_qualification_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: UserSession,
    user_text: str,
) -> None:
    if wants_manager(user_text):
        await _handle_manager_request(
            update,
            context,
            "Клиент просит связаться с менеджером",
            user_message=user_text,
        )
        return

    await update.message.reply_text(
        "Выберите вариант ответа кнопкой под вопросом. "
        "Если кнопок не видно — напишите /reset."
    )


async def _finish_qualification(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: UserSession,
    llm: AssistantLLM,
    retriever: KnowledgeRetriever,
) -> None:
    chat = update.effective_chat

    level, program, explanation = recommend_from_choices(session.qualification_choices)

    try:
        rag_context = retriever.retrieve_context(
            query=" ".join(session.qualification_answers),
            max_chunks=settings.max_rag_chunks,
        )
        llm_level, llm_program, llm_explanation = await llm.recommend(
            session.qualification_answers,
            rag_context,
        )
        matched_program = match_known_program(llm_program)
        if matched_program:
            level, program = matched_program.level, matched_program.title
            if llm_explanation:
                explanation = llm_explanation
        else:
            logger.warning("LLM returned unknown program, using rule-based result: %s", llm_program)
    except Exception:
        logger.warning("LLM recommendation unavailable, using rule-based result", exc_info=True)

    session.level = level
    session.recommended_program = program
    session.recommendation_text = explanation
    session.state = FlowState.AWAITING_QA_CHECK

    if chat:
        await chat.send_message(
            "Спасибо за ответы! Подбор программы готов — результат отправлю после имени и email.\n\n"
            f"{QA_CHECK_QUESTION}"
        )


async def _handle_qa(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: UserSession,
    llm: AssistantLLM,
    retriever: KnowledgeRetriever,
    knowledge: list,
    user_text: str,
) -> None:
    if wants_manager(user_text):
        await _handle_manager_request(
            update,
            context,
            "Клиент просит связаться с менеджером",
            user_message=user_text,
        )
        session.state = FlowState.AWAITING_QA_CHECK
        return

    if await _reply_if_off_topic(
        update,
        session,
        user_text,
        context=context,
        user_message=user_text,
    ):
        return

    retrieved = retriever.search(
        query=user_text,
        max_chunks=settings.max_rag_chunks,
    )
    rag_context = format_retrieved_context(retrieved)
    top_score = retrieved[0].similarity if retrieved else 0.0
    search_chunks = [
        KnowledgeChunk(source=item.source, text=item.text) for item in retrieved
    ]

    logger.info(
        "RAG retrieval: query=%r top_score=%.3f threshold=%.2f chunks=%s",
        user_text,
        top_score,
        settings.rag_similarity_threshold,
        format_retrieval_log(retrieved),
    )

    answer, answer_source = answer_from_search(
        user_text,
        search_chunks,
        knowledge,
        top_score=top_score,
        relevance_threshold=settings.rag_similarity_threshold,
    )
    force_escalation = False

    if not answer:
        if should_use_llm(
            top_score=top_score,
            relevance_threshold=settings.rag_similarity_threshold,
            rag_context=rag_context,
        ):
            try:
                answer = await llm.reply(
                    user_text,
                    rag_context,
                    session.qa_history,
                    extra_system=(
                        "Результат подбора программы для этого клиента ещё не озвучен. "
                        "Не называй конкретную рекомендованную программу и уровень клиента. "
                        "Отвечай только на общие вопросы о продуктах школы. "
                        "Если в контексте нет ответа — прямо скажи, что в базе знаний нет "
                        "точной информации, и предложи передать вопрос менеджеру. "
                        "Не выдумывай цены, сроки, условия и названия программ."
                    ),
                )
                answer, force_escalation = sanitize_llm_answer(answer, rag_context)
                answer_source = "llm"
            except Exception:
                logger.warning("LLM QA unavailable, using knowledge fallback", exc_info=True)
                answer, answer_source = answer_from_search(
                    user_text,
                    search_chunks,
                    knowledge,
                    top_score=top_score,
                    relevance_threshold=settings.rag_similarity_threshold,
                )
                if not answer:
                    answer = unknown_qa_fallback()
                    answer_source = "unknown_fallback"
        else:
            answer = unknown_qa_fallback()
            answer_source = "unknown_fallback"

    logger.info(
        "QA answer: query=%r source=%s top_score=%.3f answer_preview=%r",
        user_text,
        answer_source or "unknown",
        top_score,
        answer[:120] if answer else "",
    )

    session.qa_history.append({"role": "user", "content": user_text})
    session.qa_history.append({"role": "assistant", "content": answer})
    _trim_qa_history(session)

    session.state = FlowState.AWAITING_QA_CHECK

    if force_escalation or answer_needs_escalation(answer):
        await _handle_manager_request(
            update,
            context,
            "Вопрос требует ответа менеджера",
            user_message=user_text,
        )
        await update.message.reply_text(f"{answer}\n\n{QA_CHECK_QUESTION}")
        return

    await update.message.reply_text(f"{answer}\n\n{QA_CHECK_QUESTION}")


async def _handle_qa_check(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: UserSession,
    llm: AssistantLLM,
    retriever: KnowledgeRetriever,
    knowledge: list,
    user_text: str,
) -> None:
    if wants_manager(user_text):
        await _handle_manager_request(
            update,
            context,
            "Клиент просит связаться с менеджером",
            user_message=user_text,
        )
        return

    if has_no_more_questions(user_text):
        session.state = FlowState.COLLECT_NAME
        await update.message.reply_text(
            "Отлично! Чтобы получить итоговую рекомендацию, напишите ваше имя."
        )
        return

    if await _reply_if_off_topic(
        update,
        session,
        user_text,
        context=context,
        user_message=user_text,
    ):
        return

    session.state = FlowState.QA
    await _handle_qa(update, context, session, llm, retriever, knowledge, user_text)


async def _handle_collect_name(
    update: Update,
    session: UserSession,
    user_text: str,
) -> None:
    if not is_valid_name(user_text):
        await update.message.reply_text("Пожалуйста, укажите имя (от 2 символов, только буквы).")
        return

    session.name = user_text.strip()
    session.state = FlowState.COLLECT_EMAIL
    await update.message.reply_text("Спасибо! Теперь укажите ваш email.")


async def _handle_collect_email(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: UserSession,
    user_text: str,
) -> None:
    email = parse_email(user_text)
    if not email:
        await update.message.reply_text(
            "Пожалуйста, укажите корректный email, например: name@gmail.com или name@yandex.ru"
        )
        return

    session.email = email
    user = update.effective_user

    saved = await submit_lead(
        name=session.name or "",
        email=session.email,
        level=session.level or "",
        recommended_program=session.recommended_program or "",
        qualification_answers=session.qualification_answers,
        telegram_user_id=user.id if user else None,
        telegram_username=user.username if user else None,
    )

    await notify_manager_lead(
        bot=context.bot,
        user=user,
        session=session,
    )

    session.state = FlowState.DONE

    result = (
        f"Готово, {session.name}!\n\n"
        f"Ваш уровень: {session.level}\n"
        f"Рекомендуемая программа: «{session.recommended_program}»\n"
        f"{session.recommendation_text}"
    )

    if saved:
        await update.message.reply_text(
            f"{result}\n\nДанные отправлены на {session.email}. Менеджер свяжется с вами."
        )
    else:
        await update.message.reply_text(
            f"{result}\n\nМенеджер свяжется с вами."
        )


def _trim_qa_history(session: UserSession) -> None:
    if len(session.qa_history) > settings.max_history_messages:
        session.qa_history = session.qa_history[-settings.max_history_messages :]
