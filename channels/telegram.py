import asyncio
import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from agent import get_response

# Per-user conversation history (in-memory, resets on restart)
_histories: dict[int, list[dict]] = {}

MAX_MESSAGE_LENGTH = 4096


async def _send_typing(context: ContextTypes.DEFAULT_TYPE, chat_id: int, stop: asyncio.Event) -> None:
    """Send typing action every 4s while the agent is thinking."""
    while not stop.is_set():
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(4)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    _histories[uid] = []
    await update.message.reply_text(
        "Привет! Я ассистент на базе Claude.\n\n"
        "Команды:\n"
        "/reset — очистить историю диалога\n"
        "/help — помощь"
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _histories[update.effective_user.id] = []
    await update.message.reply_text("История диалога очищена.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "/start — начать заново\n"
        "/reset — очистить историю\n"
        "/help — это сообщение"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    text = update.message.text.strip()
    if not text:
        return

    history = _histories.setdefault(uid, [])
    history.append({"role": "user", "content": text})

    stop = asyncio.Event()
    typing_task = asyncio.create_task(
        _send_typing(context, update.effective_chat.id, stop)
    )

    try:
        response = await asyncio.to_thread(get_response, list(history))
    finally:
        stop.set()
        typing_task.cancel()

    history.append({"role": "assistant", "content": response})

    # Telegram caps messages at 4096 chars
    for i in range(0, max(len(response), 1), MAX_MESSAGE_LENGTH):
        await update.message.reply_text(response[i : i + MAX_MESSAGE_LENGTH])


def run() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Telegram bot is running. Press Ctrl+C to stop.")
    app.run_polling()
