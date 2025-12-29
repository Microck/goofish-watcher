from typing import TYPE_CHECKING

import discord
from discord import app_commands

from db.models import ScanStatus
from db.store import store

if TYPE_CHECKING:
    from bot.main import GoofishBot


@app_commands.guild_install()
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class StatsCommands(app_commands.Group):
    def __init__(self, bot: "GoofishBot"):
        super().__init__(name="stats", description="View statistics")
        self.bot = bot

    @app_commands.command(name="query", description="Show statistics for a query")
    @app_commands.describe(query_id="Query ID to view stats")
    async def query_stats(
        self,
        interaction: discord.Interaction,
        query_id: int,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        query = await store.get_query(query_id)
        if not query:
            await interaction.followup.send(f"Query #{query_id} not found")
            return

        scans = await store.get_recent_scans(query_id, limit=100)
        total_scans = len(scans)
        successful = sum(1 for s in scans if s.status.value == "completed")
        failed = sum(1 for s in scans if s.status.value == "failed")
        total_found = sum(s.listings_found for s in scans)
        total_new = sum(s.listings_new for s in scans)
        total_notified = sum(s.listings_notified for s in scans)

        embed = discord.Embed(
            title=f"Stats: {query.keyword}",
            color=discord.Color.blue(),
        )
        status_val = "Enabled" if query.enabled else "Disabled"
        embed.add_field(name="Status", value=status_val, inline=True)
        embed.add_field(name="Interval", value=f"{query.interval_minutes}m", inline=True)
        embed.add_field(name="AI Threshold", value=f"{query.ai_threshold:.0%}", inline=True)
        embed.add_field(name="Total Scans", value=str(total_scans), inline=True)
        embed.add_field(name="Successful", value=str(successful), inline=True)
        embed.add_field(name="Failed", value=str(failed), inline=True)
        embed.add_field(name="Listings Found", value=str(total_found), inline=True)
        embed.add_field(name="New Listings", value=str(total_new), inline=True)
        embed.add_field(name="Notified", value=str(total_notified), inline=True)

        if scans:
            last_scan = scans[0]
            embed.add_field(
                name="Last Scan",
                value=f"{last_scan.started_at.strftime('%Y-%m-%d %H:%M')} UTC",
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="overview", description="Show overall bot statistics")
    async def overview(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        queries = await store.get_all_queries()
        enabled = sum(1 for q in queries if q.enabled)

        stats = await store.get_global_stats()

        embed = discord.Embed(
            title="Goofish Watcher Stats",
            color=discord.Color.green(),
        )
        embed.add_field(name="Total Queries", value=str(len(queries)), inline=True)
        embed.add_field(name="Enabled", value=str(enabled), inline=True)
        embed.add_field(name="Disabled", value=str(len(queries) - enabled), inline=True)
        embed.add_field(name="Total Scans (24h)", value=str(stats["scans_24h"]), inline=True)
        notif_24h = str(stats["notifications_24h"])
        embed.add_field(name="Notifications (24h)", value=notif_24h, inline=True)
        embed.add_field(name="Listings Tracked", value=str(stats["listings_tracked"]), inline=True)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="health", description="Check system health")
    async def health(self, interaction: discord.Interaction) -> None:
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.NotFound:
            return  # Interaction expired

        from core.scanner import goofish_client

        try:
            auth_ok = await goofish_client.check_auth()
        except Exception:
            auth_ok = False

        recent_failures = await store.get_recent_failures(hours=1)

        status_emoji = "✅" if auth_ok and recent_failures < 3 else "⚠️" if auth_ok else "❌"

        embed = discord.Embed(
            title=f"{status_emoji} System Health",
            color=discord.Color.green() if auth_ok else discord.Color.red(),
        )
        auth_val = "✅ Valid" if auth_ok else "❌ Expired"
        embed.add_field(name="Goofish Auth", value=auth_val, inline=True)
        embed.add_field(name="Failures (1h)", value=str(recent_failures), inline=True)

        if not auth_ok:
            embed.add_field(
                name="⚠️ Action Required",
                value="Cookie expired. Update cookies.json and restart.",
                inline=False,
            )

        try:
            await interaction.followup.send(embed=embed)
        except discord.NotFound:
            pass  # Interaction expired

    @app_commands.command(name="logs", description="Show recent scan logs")
    @app_commands.describe(
        query_id="Query ID (optional, shows all if not specified)",
        limit="Number of scans to show (default: 10)",
    )
    async def logs(
        self,
        interaction: discord.Interaction,
        query_id: int | None = None,
        limit: int = 10,
    ) -> None:
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.NotFound:
            return

        limit = min(limit, 25)

        if query_id:
            query = await store.get_query(query_id)
            if not query:
                try:
                    await interaction.followup.send(f"Query #{query_id} not found")
                except discord.NotFound:
                    pass
                return
            scans = await store.get_recent_scans(query_id, limit=limit)
            title = f"Recent Scans: {query.keyword}"
        else:
            scans = await store.get_all_recent_scans(limit=limit)
            title = "Recent Scans (All Queries)"

        if not scans:
            try:
                await interaction.followup.send("No scans found")
            except discord.NotFound:
                pass
            return

        lines = []
        for s in scans:
            status_emoji = "✅" if s.status == ScanStatus.COMPLETED else "❌" if s.status == ScanStatus.FAILED else "🔄"
            time_str = s.started_at.strftime("%m/%d %H:%M")
            line = f"`{time_str}` {status_emoji} Q#{s.query_id}: {s.listings_found} found, {s.listings_new} new, {s.listings_notified} notified"
            if s.error_message:
                line += f"\n└ ⚠️ {s.error_message[:50]}"
            lines.append(line)

        embed = discord.Embed(
            title=title,
            description="\n".join(lines),
            color=discord.Color.blue(),
        )

        try:
            await interaction.followup.send(embed=embed)
        except discord.NotFound:
            pass
