import asyncio
import logging

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from src.config import settings
from src.flow import handle_flow_callback, handle_flow_message, reset_session, start_flow
from src.llm import AssistantLLM
from src.rag import load_knowledge

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

HELP_MESSAGE = (
    "Я помогу подобрать курс:\n"
    "1. Короткий тест из 4 вопросов — ответы кнопками\n"
    "2. Подберу программу и отвечу на вопросы\n"
    "3. Для итога попрошу имя и email\n\n"
    "/start — начать подбор\n"
    "/reset — начать заново"
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start_flow(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_MESSAGE)


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reset_session(context)
    await start_flow(update, context)


def main() -> None:
    knowledge = load_knowledge(settings.knowledge_dir)
    logger.info("Loaded %s knowledge chunks from %s", len(knowledge), settings.knowledge_dir)

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .build()
    )
    application.bot_data["llm"] = AssistantLLM()
    application.bot_data["knowledge"] = knowledge

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CallbackQueryHandler(handle_flow_callback, pattern=r"^quiz:"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_flow_message))

    logger.info("Bot is starting...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
