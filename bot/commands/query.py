from typing import TYPE_CHECKING

import discord
from discord import app_commands

from db.store import store

if TYPE_CHECKING:
    from bot.main import GoofishBot


@app_commands.guild_install()
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class QueryCommands(app_commands.Group):
    def __init__(self, bot: "GoofishBot"):
        super().__init__(name="query", description="Manage Goofish watch queries")
        self.bot = bot

    @app_commands.command(name="add", description="Add a new watch query")
    @app_commands.describe(
        keyword="Search keyword",
        include="Comma-separated terms that must appear",
        exclude="Comma-separated terms to exclude",
        min_price="Minimum price filter",
        max_price="Maximum price filter",
        interval="Scan interval in minutes (60/180/360)",
        ai_threshold="AI relevance threshold (0.0-1.0)",
    )
    async def add(
        self,
        interaction: discord.Interaction,
        keyword: str,
        include: str | None = None,
        exclude: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        interval: int = 60,
        ai_threshold: float = 0.7,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if interval not in (60, 180, 360):
            await interaction.followup.send("Interval must be 60, 180, or 360 minutes")
            return

        include_terms = [t.strip() for t in include.split(",")] if include else []
        exclude_terms = [t.strip() for t in exclude.split(",")] if exclude else []

        query_id = await store.add_query(
            keyword=keyword,
            include_terms=include_terms,
            exclude_terms=exclude_terms,
            min_price=min_price,
            max_price=max_price,
            interval_minutes=interval,
            ai_threshold=ai_threshold,
        )

        if self.bot.watcher:
            await self.bot.watcher.schedule_query(query_id)

        await interaction.followup.send(f"Query #{query_id} added: `{keyword}`")

    @app_commands.command(name="list", description="List all watch queries")
    async def list_queries(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        queries = await store.get_all_queries()
        if not queries:
            await interaction.followup.send("No queries configured")
            return

        lines = []
        for q in queries:
            status = "✓" if q.enabled else "✗"
            lines.append(f"#{q.id} [{status}] `{q.keyword}` ({q.interval_minutes}m)")

        await interaction.followup.send("\n".join(lines))

    @app_commands.command(name="enable", description="Enable a query")
    @app_commands.describe(query_id="Query ID to enable")
    async def enable(self, interaction: discord.Interaction, query_id: int) -> None:
        await interaction.response.defer(ephemeral=True)

        success = await store.update_query(query_id, enabled=True)
        if not success:
            await interaction.followup.send(f"Query #{query_id} not found")
            return

        if self.bot.watcher:
            await self.bot.watcher.schedule_query(query_id)

        await interaction.followup.send(f"Query #{query_id} enabled")

    @app_commands.command(name="disable", description="Disable a query")
    @app_commands.describe(query_id="Query ID to disable")
    async def disable(self, interaction: discord.Interaction, query_id: int) -> None:
        await interaction.response.defer(ephemeral=True)

        success = await store.update_query(query_id, enabled=False)
        if not success:
            await interaction.followup.send(f"Query #{query_id} not found")
            return

        if self.bot.watcher:
            self.bot.watcher.unschedule_query(query_id)

        await interaction.followup.send(f"Query #{query_id} disabled")

    @app_commands.command(name="remove", description="Remove a query")
    @app_commands.describe(query_id="Query ID to remove")
    async def remove(self, interaction: discord.Interaction, query_id: int) -> None:
        await interaction.response.defer(ephemeral=True)

        if self.bot.watcher:
            self.bot.watcher.unschedule_query(query_id)

        success = await store.delete_query(query_id)
        if not success:
            await interaction.followup.send(f"Query #{query_id} not found")
            return

        await interaction.followup.send(f"Query #{query_id} removed")

    @app_commands.command(name="test", description="Run a query immediately")
    @app_commands.describe(query_id="Query ID to test")
    async def test(self, interaction: discord.Interaction, query_id: int) -> None:
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.errors.NotFound:
            return

        query = await store.get_query(query_id)
        if not query:
            try:
                await interaction.followup.send(f"Query #{query_id} not found")
            except discord.errors.NotFound:
                pass
            return

        if self.bot.watcher:
            try:
                await interaction.followup.send(f"Running query #{query_id}...")
            except discord.errors.NotFound:
                pass
            await self.bot.watcher.run_scan(query)
            try:
                await interaction.followup.send(f"Query #{query_id} scan complete")
            except discord.errors.NotFound:
                pass
        else:
            try:
                await interaction.followup.send("Watcher not initialized")
            except discord.errors.NotFound:
                pass
