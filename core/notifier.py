import json
import logging

import discord

from config import settings
from core.parser import Listing
from core.notifications.manager import notification_manager
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
    ) -> tuple[bool, dict]:
        discord_success = await self._send_discord_dm(listing, query, ai_confidence, ai_reason)

        other_channels = await self._send_to_other_channels(listing, ai_reason)

        return discord_success, other_channels

    async def _send_discord_dm(
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

        price_display = f"¥{listing.price:,.2f}"
        if listing.original_price and listing.original_price != "暂无":
            price_display += f" (原价: {listing.original_price})"
        embed.add_field(name="Price", value=price_display, inline=True)

        embed.add_field(name="Location", value=listing.location or "Unknown", inline=True)
        embed.add_field(name="Query", value=f"#{query.id}: {query.keyword}", inline=True)

        if listing.wants_count is not None:
            embed.add_field(name="Want Count", value=f"{listing.wants_count}人想要", inline=True)

        if ai_confidence is not None:
            embed.add_field(name="AI Confidence", value=f"{ai_confidence:.0%}", inline=True)
        if ai_reason:
            embed.add_field(name="AI Reason", value=ai_reason[:100], inline=False)

        # Seller reputation information
        if listing.seller_registration_days > 0:
            reg_text = f"{listing.seller_registration_days}天"
            if listing.seller_registration_days >= 365:
                years = listing.seller_registration_days // 365
                reg_text = f"{years}年"
            embed.add_field(name="Seller Registration", value=reg_text, inline=True)

        if listing.seller_rating > 0:
            embed.add_field(name="Seller Rating", value=f"{listing.seller_rating:.0%}", inline=True)

        if listing.reputation_score > 0:
            embed.add_field(
                name="Reputation Score", value=f"{listing.reputation_score:.0f}", inline=True
            )

        if listing.tags:
            tags_str = ", ".join(listing.tags[:5])
            embed.add_field(name="Tags", value=tags_str, inline=False)

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

    async def _send_to_other_channels(self, listing: Listing, reason: str | None) -> dict:
        product_data = {
            "title": listing.title,
            "price": listing.price,
            "price_str": f"¥{listing.price:,.2f}",
            "location": listing.location,
            "detail_url": listing.detail_url,
            "image_url": listing.image_url,
            "seller_name": listing.seller_name,
            "seller_rating": listing.seller_rating,
            "wants_count": listing.wants_count,
            "tags": listing.tags,
        }

        return await notification_manager.send_to_all(product_data, reason or "")
