import asyncio
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import discord
from discord import app_commands

from bot.cogs.watcher import WatcherCog
from bot.commands.alert import AlertCommands
from bot.commands.logs import LogsCommands
from bot.commands.query import QueryCommands
from bot.commands.stats import StatsCommands
from config import settings
from db.store import store

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
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.watcher: WatcherCog | None = None

    async def setup_hook(self) -> None:
        await store.connect()
        log.info("Database connected")

        query_commands = QueryCommands(self)
        self.tree.add_command(query_commands)

        alert_commands = AlertCommands(self)
        self.tree.add_command(alert_commands)

        stats_commands = StatsCommands(self)
        self.tree.add_command(stats_commands)

        logs_commands = LogsCommands(self)
        self.tree.add_command(logs_commands)

        self.watcher = WatcherCog(self)
        await self.watcher.start()
        log.info("Watcher started")

        await self.tree.sync()
        log.info("Commands synced")

    async def on_ready(self) -> None:
        log.info(f"Logged in as {self.user}")

    async def close(self) -> None:
        if self.watcher:
            await self.watcher.stop()
        await store.close()
        await super().close()


async def main() -> None:
    bot = GoofishBot()
    async with bot:
        await bot.start(settings.discord_bot_token)


if __name__ == "__main__":
    asyncio.run(main())
