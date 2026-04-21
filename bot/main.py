"""Discord bot entry point for Goofish Watcher.

Initialises the Discord client, registers slash commands,
starts the webhook receiver, and manages the bot lifecycle.
"""

import asyncio
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import discord
from discord import app_commands

from bot.commands.login import LoginCommands
from config import settings
from core.scanner import goofish_client
from core.webhook_receiver import WebhookReceiver

log_dir = Path("./logs")
log_dir.mkdir(exist_ok=True)

log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
log_level = getattr(logging, settings.log_level)

logging.basicConfig(level=log_level, format=log_format)

file_handler = RotatingFileHandler(
    log_dir / "goofish-watcher.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
file_handler.setFormatter(logging.Formatter(log_format))
file_handler.setLevel(log_level)
logging.getLogger().addHandler(file_handler)

log = logging.getLogger(__name__)


class GoofishBot(discord.Client):
    """Discord bot that bridges Goofish/Xianyu with Discord.

    Manages QR-code login, webhook notifications from ai-goofish-monitor,
    and Discord DM forwarding of listing alerts.
    """

    def __init__(self):
        """Initialise the bot with default intents and an empty command tree."""
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.webhook_receiver: WebhookReceiver | None = None

    async def setup_hook(self) -> None:
        """Register slash commands and start the webhook HTTP receiver."""
        login_commands = LoginCommands(self)
        self.tree.add_command(login_commands)

        # Start webhook receiver (ai-goofish-monitor -> this bot -> Discord DM)
        self.webhook_receiver = WebhookReceiver(self)
        await self.webhook_receiver.start(
            host=settings.webhook_host,
            port=settings.webhook_port,
            path=settings.webhook_path,
            secret=settings.webhook_secret,
        )

        await self.tree.sync()
        log.info("Commands synced")

    async def on_ready(self) -> None:
        """Log a message when the bot successfully connects."""
        log.info(f"Logged in as {self.user}")

    async def close(self) -> None:
        """Gracefully shut down the webhook receiver, browser, and Discord client."""
        if self.webhook_receiver:
            await self.webhook_receiver.stop()
        await goofish_client.close()
        await super().close()


async def main() -> None:
    """Create and start the Discord bot."""
    bot = GoofishBot()
    async with bot:
        await bot.start(settings.discord_bot_token)


if __name__ == "__main__":
    asyncio.run(main())
