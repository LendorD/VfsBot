"""Telegram-бот: диспетчер, хендлеры, клавиатуры и состояния FSM."""

from telegram_bot.dispatcher import create_bot, create_dispatcher, setup_bot_commands

__all__ = ["create_bot", "create_dispatcher", "setup_bot_commands"]
