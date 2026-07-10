import logging

from telegram import User
from telegram.ext import ExtBot

from src.config import settings
from src.session import UserSession

logger = logging.getLogger(__name__)


async def notify_manager(bot: ExtBot, text: str) -> bool:
    if not settings.manager_telegram_chat_id:
        logger.warning("MANAGER_TELEGRAM_CHAT_ID is not set, notification skipped")
        return False

    try:
        await bot.send_message(
            chat_id=int(settings.manager_telegram_chat_id),
            text=text,
        )
        return True
    except Exception:
        logger.exception(
            "Failed to notify manager (chat_id=%s)",
            settings.manager_telegram_chat_id,
        )
        return False


def _format_telegram_contact(user: User | None) -> str:
    if user and user.username:
        return f"Telegram: @{user.username}"
    return ""


def _format_client_contact(user: User | None, session: UserSession) -> str:
    lines: list[str] = []
    if session.name:
        lines.append(f"Имя: {session.name}")
    if session.email:
        lines.append(f"Email: {session.email}")
    telegram = _format_telegram_contact(user)
    if telegram:
        lines.append(telegram)
    return "\n".join(lines) if lines else "Контакт: не указан"


async def notify_manager_escalation(
    bot: ExtBot,
    user: User | None,
    session: UserSession,
    question: str,
    reason: str,
) -> bool:
    message = (
        "⚠️ Нужен менеджер\n\n"
        f"Причина: {reason}\n"
        f"Сообщение клиента: {question}\n\n"
        f"{_format_client_contact(user, session)}"
    )
    return await notify_manager(bot, message)


async def notify_manager_lead(
    bot: ExtBot,
    user: User | None,
    session: UserSession,
) -> bool:
    lines = [
        "✅ Новая заявка",
        "",
        f"Имя: {session.name or '—'}",
        f"Email: {session.email or '—'}",
        f"Уровень: {session.level or '—'}",
        f"Программа: {session.recommended_program or '—'}",
    ]
    telegram = _format_telegram_contact(user)
    if telegram:
        lines.append(telegram)
    message = "\n".join(lines)
    return await notify_manager(bot, message)
