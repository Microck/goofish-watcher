import logging

import discord

from config import settings
from core.parser import Listing
from db.models import Query

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self, bot: discord.Client):
        self.bot = bot

    async def send_listing(
        self,
        listing: Listing,
        query: Query,
        ai_confidence: float | None = None,
        ai_reason: str | None = None,
    ) -> bool:
        try:
            user = await self.bot.fetch_user(settings.discord_user_id)
            if user is None:
                log.error(f"User {settings.discord_user_id} not found")
                return False
        except discord.NotFound:
            log.error(f"User {settings.discord_user_id} not found")
            return False
        except Exception as e:
            log.error(f"Failed to fetch user: {e}")
            return False

        embed = discord.Embed(
            title=listing.title[:256],
            url=listing.detail_url,
            color=discord.Color.green(),
        )
        embed.add_field(name="Price", value=f"¥{listing.price:,.2f}", inline=True)
        embed.add_field(name="Location", value=listing.location or "Unknown", inline=True)
        embed.add_field(name="Query", value=f"#{query.id}: {query.keyword}", inline=True)

        if ai_confidence is not None:
            embed.add_field(name="AI Confidence", value=f"{ai_confidence:.0%}", inline=True)
        if ai_reason:
            embed.add_field(name="AI Reason", value=ai_reason[:100], inline=False)

        if listing.image_url:
            embed.set_thumbnail(url=listing.image_url)

        embed.set_footer(text=f"Seller: {listing.seller_name}")

        try:
            await user.send(embed=embed)
            return True
        except discord.Forbidden:
            log.error("Cannot send DM to user - DMs may be disabled")
            return False
        except discord.HTTPException as e:
            log.error(f"Failed to send notification: {e}")
            return False
