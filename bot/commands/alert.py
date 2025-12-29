from typing import TYPE_CHECKING

import discord
from discord import app_commands

from db.store import store

if TYPE_CHECKING:
    from bot.main import GoofishBot


@app_commands.guild_install()
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class AlertCommands(app_commands.Group):
    def __init__(self, bot: "GoofishBot"):
        super().__init__(name="alert", description="Manage alert notifications")
        self.bot = bot

    @app_commands.command(name="mark", description="Add a label to a notification")
    @app_commands.describe(
        notification_id="Notification ID to label",
        label="Label to apply (e.g., 'interested', 'bought', 'spam')",
    )
    async def mark(
        self,
        interaction: discord.Interaction,
        notification_id: int,
        label: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        notifications = await store.get_notification_by_id(notification_id)
        if not notifications:
            await interaction.followup.send(f"Notification #{notification_id} not found")
            return

        await store.add_label(notification_id, label.strip().lower())
        await interaction.followup.send(f"Label `{label}` added to notification #{notification_id}")

    @app_commands.command(name="labels", description="List labels for a notification")
    @app_commands.describe(notification_id="Notification ID to view labels")
    async def labels(
        self,
        interaction: discord.Interaction,
        notification_id: int,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        labels = await store.get_labels(notification_id)
        if not labels:
            await interaction.followup.send(f"No labels for notification #{notification_id}")
            return

        label_list = ", ".join(f"`{lbl.label}`" for lbl in labels)
        await interaction.followup.send(f"Labels for #{notification_id}: {label_list}")
