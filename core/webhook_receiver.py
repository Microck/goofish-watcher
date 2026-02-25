import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import discord
from aiohttp import web

from config import settings

log = logging.getLogger(__name__)


def _truncate(text: str, limit: int = 1800) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _extract_title_content(payload: Any) -> tuple[str, str]:
    if isinstance(payload, dict):
        title = (
            payload.get("title")
            or payload.get("notification_title")
            or payload.get("subject")
            or "Goofish Monitor"
        )
        content = payload.get("content") or payload.get("message") or payload.get("body") or ""
        if not content:
            # Sometimes the payload is just a dict with a single text field.
            content = payload.get("text") or ""
        return str(title), str(content)

    if isinstance(payload, str):
        return "Goofish Monitor", payload

    return "Goofish Monitor", str(payload)


async def _send_discord_dm(bot: discord.Client, title: str, content: str, raw: Any) -> None:
    user_id = settings.discord_user_id
    if not user_id:
        log.warning("DISCORD_USER_ID not set; dropping webhook notification")
        return

    try:
        user = await bot.fetch_user(user_id)
    except Exception as e:
        log.error(f"Failed to fetch Discord user {user_id}: {e}")
        return

    embed = discord.Embed(
        title=(title or "Goofish Monitor")[:256],
        description=_truncate(content or "(empty)", 4000),
        color=discord.Color.blurple(),
    )

    if raw is not None and raw != "":
        try:
            raw_text = json.dumps(raw, ensure_ascii=False, indent=2)
        except Exception:
            raw_text = str(raw)
        embed.add_field(name="Raw", value=f"```json\n{_truncate(raw_text, 900)}\n```", inline=False)

    try:
        await user.send(embed=embed)
    except discord.Forbidden:
        log.error("Cannot send DM to user (DMs disabled?)")
    except discord.HTTPException as e:
        log.error(f"Failed to send DM: {e}")


@dataclass
class WebhookReceiver:
    bot: discord.Client

    _runner: web.AppRunner | None = None
    _site: web.TCPSite | None = None
    _secret: str = ""
    _path: str = "/webhook/ai-goofish-monitor"

    async def start(self, host: str, port: int, path: str, secret: str) -> None:
        if self._runner:
            return

        self._secret = secret or ""
        self._path = path or "/webhook/ai-goofish-monitor"

        app = web.Application()
        app.router.add_route("*", self._path, self._handle)

        self._runner = web.AppRunner(app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, host=host, port=port)
        await self._site.start()

        log.info(f"Webhook receiver listening on http://{host}:{port}{self._path}")

    async def stop(self) -> None:
        if not self._runner:
            return

        try:
            await self._runner.cleanup()
        finally:
            self._runner = None
            self._site = None

    async def _handle(self, request: web.Request) -> web.StreamResponse:
        if self._secret:
            header_secret = request.headers.get("x-webhook-secret") or request.headers.get(
                "X-Webhook-Secret"
            )
            query_secret = request.query.get("secret")
            if (header_secret or query_secret) != self._secret:
                return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

        raw: Any = None
        payload: Any = None

        # Prefer JSON when possible; otherwise accept form/text.
        ctype = (request.content_type or "").lower()
        try:
            if "json" in ctype:
                payload = await request.json()
            elif "application/x-www-form-urlencoded" in ctype or "multipart/form-data" in ctype:
                form = await request.post()
                payload = dict(form)
            else:
                payload = await request.text()
        except Exception:
            payload = await request.text()

        raw = payload
        title, content = _extract_title_content(payload)

        # Do not block webhook response on Discord API.
        asyncio.create_task(_send_discord_dm(self.bot, title, content, raw))

        return web.json_response({"ok": True})
