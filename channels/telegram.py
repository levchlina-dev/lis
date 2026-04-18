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
from channels.pc import run_agent

MAX_MSG = 4000  # Telegram limit is 4096
_histories: dict[int, list[dict]] = {}


# ── helpers ───────────────────────────────────────────────────────────────────

async def _reply(update: Update, text: str) -> None:
    """Send long text splitting into chunks if needed."""
    text = text.strip()
    if not text:
        return
    for i in range(0, max(len(text), 1), MAX_MSG):
        await update.message.reply_text(text[i : i + MAX_MSG])


# ── commands ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _histories[update.effective_user.id] = []
    await _reply(update,
        "👋 Привет! Я агент на базе Claude.\n\n"
        "Режимы:\n"
        "• Просто пишите — обычный чат\n"
        "• /agent <задача> — агент выполнит задачу на сервере\n\n"
        "Команды:\n"
        "/reset — очистить историю чата\n"
        "/help — помощь"
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _histories[update.effective_user.id] = []
    await _reply(update, "🗑 История очищена.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(update,
        "Как пользоваться:\n\n"
        "💬 Просто написать — чат с ассистентом\n"
        "/agent установи nginx — агент выполнит задачу на сервере\n"
        "/reset — очистить историю диалога\n\n"
        "Агент умеет:\n"
        "• Запускать команды на сервере\n"
        "• Читать и писать файлы\n"
        "• Выполнять многошаговые задачи\n"
        "• Анализировать данные"
    )


async def cmd_agent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run PC agent for a task specified after /agent."""
    task = " ".join(context.args).strip()
    if not task:
        await _reply(update, "Укажите задачу: /agent <задача>")
        return
    await _run_agent_task(update, context, task)


# ── agent runner ──────────────────────────────────────────────────────────────

async def _run_agent_task(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    task: str,
) -> None:
    status_msg = await update.message.reply_text("⏳ Агент начинает работу...")
    log_lines: list[str] = []
    loop = asyncio.get_event_loop()

    async def update_status(new_text: str) -> None:
        try:
            await status_msg.edit_text(new_text[:MAX_MSG])
        except Exception:
            pass

    def on_update(type_: str, content: str) -> None:
        if type_ == "text":
            line = f"💬 {content}"
        elif type_ == "tool":
            line = f"🔧 `{content}`"
        elif type_ == "result":
            short = content[:400] + ("…" if len(content) > 400 else "")
            line = f"📤 {short}"
        elif type_ == "done":
            line = "✅ Готово"
        else:
            return

        log_lines.append(line)
        # Show last 15 lines in the status message
        text = "\n".join(log_lines[-15:])
        asyncio.run_coroutine_threadsafe(update_status(text), loop)

    await asyncio.to_thread(run_agent, task, on_update)

    # Final full summary
    final = "\n".join(log_lines)
    if len(final) > MAX_MSG:
        # Edit status + send overflow as new message
        await update_status("\n".join(log_lines[-15:]))
        await _reply(update, "📋 Полный лог:\n" + final)
    else:
        await update_status(final or "✅ Готово")


# ── regular chat ──────────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    text = update.message.text.strip()
    if not text:
        return

    history = _histories.setdefault(uid, [])
    history.append({"role": "user", "content": text})

    stop = asyncio.Event()

    async def keep_typing() -> None:
        while not stop.is_set():
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id, action="typing"
            )
            await asyncio.sleep(4)

    typing_task = asyncio.create_task(keep_typing())
    try:
        response = await asyncio.to_thread(get_response, list(history))
    finally:
        stop.set()
        typing_task.cancel()

    history.append({"role": "assistant", "content": response})
    await _reply(update, response)


# ── entry point ───────────────────────────────────────────────────────────────

def run() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("agent", cmd_agent))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Telegram bot is running. Press Ctrl+C to stop.")
    app.run_polling()
