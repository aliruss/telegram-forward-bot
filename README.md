# Telegram Bot (Python)

A simple Telegram bot built with Python.

## Features

- `/start` welcome command
- `/help` usage command
- `/echo <text>` command
- Optional auto-relay of all non-command messages to a target chat (re-sent, not forwarded)
- SQLite-backed blocked words list
- Admin-only commands to manage blocked words
- Admin-only commands to set/clear/show relay signature
- Text/caption sanitization before sending to destination
- Optional signature appended to relayed message text/caption

## Admin Commands

- `/addword <word>`: add a blocked word
- `/removeword <word>`: remove a blocked word
- `/listwords`: list current blocked words
- `/setsignature <text>`: set signature appended to relayed messages
- `/clearsignature`: remove signature
- `/showsignature`: show current signature

Only users listed in `ADMIN_IDS` can use these commands.

## Setup

1. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables:

   ```bash
   cp .env.example .env
   ```

   Set:
   - `BOT_TOKEN` (required)
   - `FORWARD_CHAT_ID` (optional)
   - `ADMIN_IDS` (optional but required for admin management commands)
   - `FILTER_DB_PATH` (optional)
   - `SIGNATURE_TEXT` (optional)

   The bot reads `.env` automatically from either the current working directory or bot script directory.

4. Run the bot:

   ```bash
   python bot.py
   ```

## Word Filtering Behavior

When a non-command message arrives, the bot:

1. Loads blocked words from SQLite database.
2. Removes blocked words from text/caption (case-insensitive).
3. Appends signature (if configured).
4. Sends the sanitized result to destination chat.

If message text becomes empty after sanitization, only signature is sent when configured; otherwise nothing is sent for plain text messages.

## Notes

- To get a bot token, create a bot with [@BotFather](https://t.me/BotFather).
- To get a chat ID, you can use helper bots like [@userinfobot](https://t.me/userinfobot) or inspect updates.
