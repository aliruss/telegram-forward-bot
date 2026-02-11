#!/usr/bin/env python3
"""Simple Telegram bot using python-telegram-bot.

Features:
- /start: welcome message
- /help: usage instructions
- /echo <text>: repeats text
- Re-sends any non-command message to a configured chat

Environment variables:
- BOT_TOKEN: Telegram Bot API token (required)
- FORWARD_CHAT_ID: Destination chat/channel ID for forwarded messages (optional)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Final, Iterable

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN_ENV: Final[str] = "BOT_TOKEN"
FORWARD_CHAT_ID_ENV: Final[str] = "FORWARD_CHAT_ID"


def _candidate_env_files(filename: str = ".env") -> Iterable[Path]:
    """Return potential .env locations in lookup order."""
    cwd_env = Path.cwd() / filename
    script_env = Path(__file__).resolve().parent / filename

    # Avoid duplicate lookups when cwd and script directory are the same.
    if cwd_env == script_env:
        return (cwd_env,)
    return (cwd_env, script_env)


def load_local_env(filename: str = ".env") -> None:
    """Load KEY=VALUE pairs from local .env files.

    Supported formats:
    - KEY=value
    - export KEY=value
    - Optional single/double quotes around value

    Existing environment values are preserved.
    """
    for env_file in _candidate_env_files(filename):
        if not env_file.exists():
            continue

        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("export "):
                line = line[len("export ") :].strip()

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)


# Load local .env values when present so local runs work out-of-the-box.
load_local_env()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    if update.message:
        await update.message.reply_html(
            f"Hi {user.mention_html()}! I am ready.\n"
            "Use /help to see available commands."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if update.message:
        await update.message.reply_text(
            "Available commands:\n"
            "/start - Start the bot\n"
            "/help - Show this message\n"
            "/echo <text> - Echo text back\n\n"
            "Any non-command message can be auto-relayed if FORWARD_CHAT_ID is set."
        )


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /echo command."""
    if not update.message:
        return

    if context.args:
        await update.message.reply_text(" ".join(context.args))
    else:
        await update.message.reply_text("Usage: /echo <text>")


async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Re-send non-command messages to a target chat if configured."""
    target_chat_id = os.getenv(FORWARD_CHAT_ID_ENV)
    message = update.message
    if not target_chat_id or not message:
        return

    try:
        if message.text:
            await context.bot.send_message(chat_id=target_chat_id, text=message.text)
        elif message.photo:
            largest = message.photo[-1]
            await context.bot.send_photo(
                chat_id=target_chat_id,
                photo=largest.file_id,
                caption=message.caption,
                caption_entities=message.caption_entities,
            )
        elif message.video:
            await context.bot.send_video(
                chat_id=target_chat_id,
                video=message.video.file_id,
                caption=message.caption,
                caption_entities=message.caption_entities,
            )
        elif message.document:
            await context.bot.send_document(
                chat_id=target_chat_id,
                document=message.document.file_id,
                caption=message.caption,
                caption_entities=message.caption_entities,
            )
        elif message.audio:
            await context.bot.send_audio(
                chat_id=target_chat_id,
                audio=message.audio.file_id,
                caption=message.caption,
                caption_entities=message.caption_entities,
            )
        elif message.voice:
            await context.bot.send_voice(
                chat_id=target_chat_id,
                voice=message.voice.file_id,
                caption=message.caption,
                caption_entities=message.caption_entities,
            )
        elif message.sticker:
            await context.bot.send_sticker(
                chat_id=target_chat_id,
                sticker=message.sticker.file_id,
            )
        elif message.animation:
            await context.bot.send_animation(
                chat_id=target_chat_id,
                animation=message.animation.file_id,
                caption=message.caption,
                caption_entities=message.caption_entities,
            )
        else:
            await context.bot.send_message(
                chat_id=target_chat_id,
                text="[Unsupported message type received]",
            )
    except Exception:
        logger.exception("Failed to relay message")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log unhandled errors."""
    logger.exception("Unhandled exception while processing update", exc_info=context.error)


def build_application() -> Application:
    """Create and configure Telegram application."""
    token = os.getenv(BOT_TOKEN_ENV)
    if not token:
        raise RuntimeError(
            f"Missing required environment variable: {BOT_TOKEN_ENV}. "
            "Set it in your environment or in a local .env file."
        )

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("echo", echo))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, relay_message))

    application.add_error_handler(on_error)
    return application


def main() -> None:
    app = build_application()
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
