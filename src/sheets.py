import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


async def submit_lead(
    *,
    name: str,
    email: str,
    level: str,
    recommended_program: str,
    qualification_answers: list[str],
    telegram_user_id: int | None = None,
    telegram_username: str | None = None,
) -> bool:
    if not settings.google_sheets_webhook_url:
        logger.warning("GOOGLE_SHEETS_WEBHOOK_URL is not set, lead not saved")
        return False

    payload = {
        "name": name,
        "email": email,
        "level": level,
        "recommended_program": recommended_program,
        "qualification_answers": qualification_answers,
        "telegram_user_id": telegram_user_id,
        "telegram_username": telegram_username,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                settings.google_sheets_webhook_url,
                json=payload,
            )
            response.raise_for_status()
        logger.info("Lead saved for %s", email)
        return True
    except Exception:
        logger.exception("Failed to submit lead to Google Sheets")
        return False
