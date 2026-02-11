#!/usr/bin/env python3
"""Simple Telegram bot using python-telegram-bot.

Features:
- /start: welcome message
- /help: usage instructions
- /echo <text>: repeats text
- Re-sends any non-command message to a configured chat
- Word filtering backed by SQLite database

Environment variables:
- BOT_TOKEN: Telegram Bot API token (required)
- FORWARD_CHAT_ID: Destination chat/channel ID for relayed messages (optional)
- ADMIN_IDS: Comma-separated Telegram user IDs that can manage filter words (optional)
- FILTER_DB_PATH: SQLite database path (optional)
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
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
ADMIN_IDS_ENV: Final[str] = "ADMIN_IDS"
FILTER_DB_PATH_ENV: Final[str] = "FILTER_DB_PATH"
DEFAULT_DB_NAME: Final[str] = "bot_filter.db"


def _candidate_env_files(filename: str = ".env") -> Iterable[Path]:
    """Return potential .env locations in lookup order."""
    cwd_env = Path.cwd() / filename
    script_env = Path(__file__).resolve().parent / filename

    if cwd_env == script_env:
        return (cwd_env,)
    return (cwd_env, script_env)


def load_local_env(filename: str = ".env") -> None:
    """Load KEY=VALUE pairs from local .env files."""
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


def get_db_path() -> Path:
    """Return SQLite database path."""
    configured = os.getenv(FILTER_DB_PATH_ENV)
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent / DEFAULT_DB_NAME


def init_db() -> None:
    """Initialize SQLite table for blocked words."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS blocked_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL UNIQUE
            )
            """
        )
        conn.commit()


def normalize_word(word: str) -> str:
    """Normalize stored words."""
    return word.strip().lower()


def add_blocked_word(word: str) -> bool:
    """Add a blocked word. Returns True if inserted."""
    normalized = normalize_word(word)
    if not normalized:
        return False

    with sqlite3.connect(get_db_path()) as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO blocked_words(word) VALUES (?)", (normalized,)
        )
        conn.commit()
        return cursor.rowcount > 0


def remove_blocked_word(word: str) -> bool:
    """Remove a blocked word. Returns True if removed."""
    normalized = normalize_word(word)
    if not normalized:
        return False

    with sqlite3.connect(get_db_path()) as conn:
        cursor = conn.execute("DELETE FROM blocked_words WHERE word = ?", (normalized,))
        conn.commit()
        return cursor.rowcount > 0


def list_blocked_words() -> list[str]:
    """Return blocked words sorted by id."""
    with sqlite3.connect(get_db_path()) as conn:
        rows = conn.execute("SELECT word FROM blocked_words ORDER BY id ASC").fetchall()
    return [row[0] for row in rows]


def sanitize_text(text: str | None) -> str | None:
    """Remove blocked words from message content while preserving line breaks."""
    if text is None:
        return None

    cleaned = text
    for word in list_blocked_words():
        if not word:
            continue
        cleaned = re.sub(re.escape(word), "", cleaned, flags=re.IGNORECASE)

    # Collapse repeated horizontal whitespace but preserve line breaks.
    cleaned = re.sub(r"[^\S\r\n]{2,}", " ", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n[ \t]+", "\n", cleaned)
    return cleaned


def parse_admin_ids() -> set[int]:
    """Parse admin IDs from environment."""
    raw = os.getenv(ADMIN_IDS_ENV, "").strip()
    if not raw:
        return set()

    admin_ids: set[int] = set()
    for value in raw.split(","):
        part = value.strip()
        if not part:
            continue
        try:
            admin_ids.add(int(part))
        except ValueError:
            logger.warning("Ignoring non-integer ADMIN_IDS value: %s", part)
    return admin_ids


def is_admin(update: Update) -> bool:
    """Return whether user is configured as admin."""
    user = update.effective_user
    if not user:
        return False
    return user.id in parse_admin_ids()


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
            "/echo <text> - Echo text back\n"
            "/addword <word> - Add blocked word (admin)\n"
            "/removeword <word> - Remove blocked word (admin)\n"
            "/listwords - List blocked words (admin)\n\n"
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


async def add_word_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add blocked word command for admins."""
    if not update.message:
        return
    if not is_admin(update):
        await update.message.reply_text("Not authorized.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /addword <word>")
        return

    word = " ".join(context.args).strip()
    if add_blocked_word(word):
        await update.message.reply_text(f"Added: {normalize_word(word)}")
    else:
        await update.message.reply_text("Word already exists or is invalid.")


async def remove_word_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove blocked word command for admins."""
    if not update.message:
        return
    if not is_admin(update):
        await update.message.reply_text("Not authorized.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /removeword <word>")
        return

    word = " ".join(context.args).strip()
    if remove_blocked_word(word):
        await update.message.reply_text(f"Removed: {normalize_word(word)}")
    else:
        await update.message.reply_text("Word not found.")


async def list_words_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List blocked words command for admins."""
    if not update.message:
        return
    if not is_admin(update):
        await update.message.reply_text("Not authorized.")
        return

    words = list_blocked_words()
    if not words:
        await update.message.reply_text("Blocked words list is empty.")
        return

    await update.message.reply_text("Blocked words:\n" + "\n".join(f"- {w}" for w in words))


async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Re-send non-command messages to a target chat if configured."""
    target_chat_id = os.getenv(FORWARD_CHAT_ID_ENV)
    message = update.message
    if not target_chat_id or not message:
        return

    safe_text = sanitize_text(message.text)
    safe_caption = sanitize_text(message.caption)

    try:
        if message.text is not None:
            if safe_text and safe_text.strip():
                await context.bot.send_message(chat_id=target_chat_id, text=safe_text)
        elif message.photo:
            largest = message.photo[-1]
            await context.bot.send_photo(
                chat_id=target_chat_id,
                photo=largest.file_id,
                caption=safe_caption,
                caption_entities=message.caption_entities if safe_caption else None,
            )
        elif message.video:
            await context.bot.send_video(
                chat_id=target_chat_id,
                video=message.video.file_id,
                caption=safe_caption,
                caption_entities=message.caption_entities if safe_caption else None,
            )
        elif message.document:
            await context.bot.send_document(
                chat_id=target_chat_id,
                document=message.document.file_id,
                caption=safe_caption,
                caption_entities=message.caption_entities if safe_caption else None,
            )
        elif message.audio:
            await context.bot.send_audio(
                chat_id=target_chat_id,
                audio=message.audio.file_id,
                caption=safe_caption,
                caption_entities=message.caption_entities if safe_caption else None,
            )
        elif message.voice:
            await context.bot.send_voice(
                chat_id=target_chat_id,
                voice=message.voice.file_id,
                caption=safe_caption,
                caption_entities=message.caption_entities if safe_caption else None,
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
                caption=safe_caption,
                caption_entities=message.caption_entities if safe_caption else None,
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

    init_db()
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("echo", echo))
    application.add_handler(CommandHandler("addword", add_word_command))
    application.add_handler(CommandHandler("removeword", remove_word_command))
    application.add_handler(CommandHandler("listwords", list_words_command))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, relay_message))

    application.add_error_handler(on_error)
    return application


def main() -> None:
    app = build_application()
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
