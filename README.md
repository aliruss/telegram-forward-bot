# Telegram Bot (Python)

A simple Telegram bot built with Python.

## Features

- `/start` welcome command
- `/help` usage command
- `/echo <text>` command
- Optional auto-forwarding of all non-command messages to a target chat

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

   The bot reads `.env` automatically (no extra package required), from either the current working directory or the bot script directory.

4. Run the bot:

   ```bash
   python bot.py
   ```

## Notes

- To get a bot token, create a bot with [@BotFather](https://t.me/BotFather).
- To get a chat ID, you can use helper bots like [@userinfobot](https://t.me/userinfobot) or inspect updates.
