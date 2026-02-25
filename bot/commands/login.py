import io
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from core.scanner import goofish_client

log = logging.getLogger(__name__)


def _truncate_discord_message(text: str, limit: int = 1900) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _short_error(text: str) -> str:
    # Playwright exceptions can include huge "Browser logs" blocks.
    return (text or "").splitlines()[0] if text else ""


if TYPE_CHECKING:
    from bot.main import GoofishBot


@app_commands.guild_install()
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
class LoginCommands(app_commands.Group):
    def __init__(self, bot: "GoofishBot"):
        super().__init__(name="login", description="Goofish login commands")
        self.bot = bot

    @app_commands.command(name="qr", description="Login via QR code")
    async def qr_login(self, interaction: discord.Interaction) -> None:
        """Trigger QR code login flow."""
        await interaction.response.defer(ephemeral=True)

        try:
            start = await goofish_client.qr_login_start()
            if not start.get("success") or not start.get("qr_png"):
                await interaction.followup.send(
                    _truncate_discord_message(
                        f"❌ Failed to start QR login: {_short_error(str(start.get('error', 'Unknown error')))}"
                    ),
                    ephemeral=True,
                )
                return

            png_bytes = start["qr_png"]
            file = discord.File(io.BytesIO(png_bytes), filename="goofish-login.png")

            embed = discord.Embed(
                title="📱 Scan QR Code with 闲鱼 App",
                description=(
                    "Scan this QR code with your 闲鱼 app to login.\n\n"
                    "After scanning, wait up to ~2 minutes for confirmation."
                ),
                color=discord.Color.green(),
            )
            embed.set_image(url="attachment://goofish-login.png")

            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
            await interaction.followup.send("⏳ Waiting for scan...", ephemeral=True)

            done = await goofish_client.qr_login_wait(timeout=120)
            if done.get("success"):
                await interaction.followup.send(
                    "✅ Login successful! Cookies saved.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    _truncate_discord_message(
                        f"❌ Login failed: {_short_error(str(done.get('error', 'Unknown error')))}"
                    ),
                    ephemeral=True,
                )

        except Exception as e:
            log.exception("/login qr failed")
            await interaction.followup.send(
                _truncate_discord_message(f"❌ Error: {str(e)}"),
                ephemeral=True,
            )

    @app_commands.command(name="status", description="Check login status")
    async def status(self, interaction: discord.Interaction) -> None:
        """Check if currently logged in."""
        await interaction.response.defer(ephemeral=True)

        try:
            is_logged_in = await goofish_client.check_auth()

            if is_logged_in:
                await interaction.followup.send("✅ Currently logged in to Goofish", ephemeral=True)
            else:
                await interaction.followup.send(
                    "❌ Not logged in. Use `/login qr` to login", ephemeral=True
                )
        except Exception as e:
            await interaction.followup.send(f"❌ Status check failed: {str(e)}", ephemeral=True)

    @app_commands.command(
        name="export_state",
        description="Export login state for ai-goofish-monitor (xianyu_state.json)",
    )
    @app_commands.describe(path="Output path (default: ./xianyu_state.json)")
    async def export_state(self, interaction: discord.Interaction, path: str | None = None) -> None:
        await interaction.response.defer(ephemeral=True)

        out_path = path or "./xianyu_state.json"
        try:
            state = await goofish_client.export_storage_state(out_path)
            cookie_count = len(state.get("cookies") or []) if isinstance(state, dict) else 0
            await interaction.followup.send(
                f"✅ Exported login state to `{out_path}` (cookies: {cookie_count})",
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                _truncate_discord_message(f"❌ Export failed: {str(e)}"),
                ephemeral=True,
            )

    @app_commands.command(
        name="export_state_file",
        description="Export login state and attach xianyu_state.json (for panel import)",
    )
    @app_commands.describe(path="Output path saved on disk (default: ./xianyu_state.json)")
    async def export_state_file(
        self, interaction: discord.Interaction, path: str | None = None
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        out_path = path or "./xianyu_state.json"
        try:
            state = await goofish_client.export_storage_state(out_path)
            cookie_count = len(state.get("cookies") or []) if isinstance(state, dict) else 0

            p = Path(out_path)
            file = discord.File(io.BytesIO(p.read_bytes()), filename=p.name or "xianyu_state.json")

            await interaction.followup.send(
                f"✅ Exported login state to `{out_path}` (cookies: {cookie_count}). Attached file:",
                file=file,
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                _truncate_discord_message(f"❌ Export failed: {str(e)}"),
                ephemeral=True,
            )
