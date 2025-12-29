from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord import app_commands

if TYPE_CHECKING:
    from bot.main import GoofishBot

LOG_FILE = Path("./logs/goofish-watcher.log")
MAX_DISCORD_MSG_LEN = 1900


@app_commands.guild_install()
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class LogsCommands(app_commands.Group):
    def __init__(self, bot: "GoofishBot"):
        super().__init__(name="logs", description="View application logs")
        self.bot = bot

    @app_commands.command(name="tail", description="Show last N lines of logs")
    @app_commands.describe(lines="Number of lines to show (default: 50, max: 500)")
    async def tail(
        self,
        interaction: discord.Interaction,
        lines: int = 50,
    ) -> None:
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.NotFound:
            return

        lines = max(1, min(lines, 500))

        if not LOG_FILE.exists():
            try:
                await interaction.followup.send("No log file found")
            except discord.NotFound:
                pass
            return

        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
                tail_lines = all_lines[-lines:]
        except Exception as e:
            try:
                await interaction.followup.send(f"Error reading logs: {e}")
            except discord.NotFound:
                pass
            return

        if not tail_lines:
            try:
                await interaction.followup.send("Log file is empty")
            except discord.NotFound:
                pass
            return

        content = "".join(tail_lines)

        if len(content) <= MAX_DISCORD_MSG_LEN:
            try:
                await interaction.followup.send(f"```\n{content}\n```")
            except discord.NotFound:
                pass
        else:
            file = discord.File(
                fp=LOG_FILE,
                filename="goofish-watcher.log",
            )
            try:
                await interaction.followup.send(
                    f"Log file too large for message. Last {lines} lines attached:",
                    file=file,
                )
            except discord.NotFound:
                pass

    @app_commands.command(name="search", description="Search logs for a pattern")
    @app_commands.describe(
        pattern="Text to search for",
        lines="Max lines to return (default: 50, max: 200)",
    )
    async def search(
        self,
        interaction: discord.Interaction,
        pattern: str,
        lines: int = 50,
    ) -> None:
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.NotFound:
            return

        lines = max(1, min(lines, 200))

        if not LOG_FILE.exists():
            try:
                await interaction.followup.send("No log file found")
            except discord.NotFound:
                pass
            return

        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
        except Exception as e:
            try:
                await interaction.followup.send(f"Error reading logs: {e}")
            except discord.NotFound:
                pass
            return

        pattern_lower = pattern.lower()
        matches = [line for line in all_lines if pattern_lower in line.lower()]
        matches = matches[-lines:]

        if not matches:
            try:
                await interaction.followup.send(f"No matches found for `{pattern}`")
            except discord.NotFound:
                pass
            return

        content = "".join(matches)

        if len(content) <= MAX_DISCORD_MSG_LEN:
            try:
                await interaction.followup.send(f"Found {len(matches)} matches:\n```\n{content}\n```")
            except discord.NotFound:
                pass
        else:
            from io import BytesIO
            file = discord.File(
                fp=BytesIO(content.encode("utf-8")),
                filename=f"search-{pattern[:20]}.log",
            )
            try:
                await interaction.followup.send(
                    f"Found {len(matches)} matches (attached):",
                    file=file,
                )
            except discord.NotFound:
                pass

    @app_commands.command(name="errors", description="Show recent errors")
    @app_commands.describe(lines="Max error lines to return (default: 50)")
    async def errors(
        self,
        interaction: discord.Interaction,
        lines: int = 50,
    ) -> None:
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.NotFound:
            return

        lines = max(1, min(lines, 200))

        if not LOG_FILE.exists():
            try:
                await interaction.followup.send("No log file found")
            except discord.NotFound:
                pass
            return

        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
        except Exception as e:
            try:
                await interaction.followup.send(f"Error reading logs: {e}")
            except discord.NotFound:
                pass
            return

        error_keywords = ["[ERROR]", "[WARNING]", "Traceback", "Exception"]
        matches = [line for line in all_lines if any(kw in line for kw in error_keywords)]
        matches = matches[-lines:]

        if not matches:
            try:
                await interaction.followup.send("No errors found")
            except discord.NotFound:
                pass
            return

        content = "".join(matches)

        if len(content) <= MAX_DISCORD_MSG_LEN:
            try:
                await interaction.followup.send(f"Found {len(matches)} error lines:\n```\n{content}\n```")
            except discord.NotFound:
                pass
        else:
            from io import BytesIO
            file = discord.File(
                fp=BytesIO(content.encode("utf-8")),
                filename="errors.log",
            )
            try:
                await interaction.followup.send(
                    f"Found {len(matches)} error lines (attached):",
                    file=file,
                )
            except discord.NotFound:
                pass

    @app_commands.command(name="download", description="Download full log file")
    async def download(self, interaction: discord.Interaction) -> None:
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.NotFound:
            return

        if not LOG_FILE.exists():
            try:
                await interaction.followup.send("No log file found")
            except discord.NotFound:
                pass
            return

        file_size = LOG_FILE.stat().st_size
        if file_size > 8 * 1024 * 1024:
            try:
                await interaction.followup.send(
                    f"Log file too large ({file_size // 1024 // 1024}MB). Use `/logs tail` instead."
                )
            except discord.NotFound:
                pass
            return

        file = discord.File(fp=LOG_FILE, filename="goofish-watcher.log")
        try:
            await interaction.followup.send("Full log file:", file=file)
        except discord.NotFound:
            pass
