import asyncio
import html
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import quote

import discord
from aiohttp import web

from config import settings

log = logging.getLogger(__name__)

_AUTH_EXPIRED_MESSAGE_PATTERNS = (
    "goofish authentication has expired",
    "update cookies.json and restart the bot",
)

_URL_RE = re.compile(r"https?://[^\s)]+")

_FX_CACHE: dict[str, float] = {"value": 0.0, "updated_at": 0.0}
_FX_CACHE_TTL_SECONDS = 6 * 60 * 60
_FX_LOCK = asyncio.Lock()

_TRANSLATION_CACHE: dict[str, str] = {}
_TRANSLATION_CACHE_MAX = 200


@dataclass
class ListingNotification:
    listing_title: str
    reason: str
    description: str
    price_raw: str
    price_cny: float | None
    goofish_url: str
    goofish_short_url: str
    superbuy_url: str
    image_url: str
    image_urls: list[str]


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
            content = payload.get("text") or ""
        return str(title), str(content)

    if isinstance(payload, str):
        return "Goofish Monitor", payload

    return "Goofish Monitor", str(payload)


def _should_drop_notification(title: str, content: str) -> bool:
    normalized_title = (title or "").strip().lower()
    normalized_content = (content or "").strip().lower()
    combined = f"{normalized_title}\n{normalized_content}"
    return any(pattern in combined for pattern in _AUTH_EXPIRED_MESSAGE_PATTERNS)


def _extract_urls(text: str) -> list[str]:
    return [m.group(0).strip().rstrip(".,") for m in _URL_RE.finditer(text or "")]


def _extract_value_by_labels(content: str, labels: tuple[str, ...]) -> str:
    for line in (content or "").splitlines():
        line = line.strip()
        lowered = line.lower()
        for label in labels:
            if lowered.startswith(label.lower()):
                return line[len(label) :].strip()
    return ""


def _parse_cny_amount(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    text = text.replace(",", "").replace(" ", "")
    text = text.replace("￥", "").replace("¥", "")

    if "万" in text:
        try:
            return float(text.replace("万", "")) * 10000.0
        except ValueError:
            return None

    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None

    try:
        return float(match.group(0))
    except ValueError:
        return None


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _translate_to_english_sync(text: str) -> str:
    source = (text or "").strip()
    if not source or not _contains_cjk(source):
        return source

    query = urllib.parse.urlencode(
        {
            "client": "gtx",
            "sl": "auto",
            "tl": "en",
            "dt": "t",
            "q": source,
        }
    )
    url = f"https://translate.googleapis.com/translate_a/single?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
        },
    )

    with urllib.request.urlopen(request, timeout=6) as response:
        body = response.read().decode("utf-8", errors="ignore")

    payload = json.loads(body)
    if not isinstance(payload, list) or not payload:
        return source

    segments = payload[0]
    if not isinstance(segments, list):
        return source

    translated_parts: list[str] = []
    for segment in segments:
        if isinstance(segment, list) and segment:
            first = segment[0]
            if isinstance(first, str):
                translated_parts.append(first)

    translated = "".join(translated_parts).strip()
    return translated or source


async def _translate_to_english(text: str) -> str:
    source = (text or "").strip()
    if not source:
        return ""
    if not _contains_cjk(source):
        return source

    cached = _TRANSLATION_CACHE.get(source)
    if cached:
        return cached

    try:
        translated = await asyncio.to_thread(_translate_to_english_sync, source)
    except Exception:
        translated = source

    if len(_TRANSLATION_CACHE) >= _TRANSLATION_CACHE_MAX:
        _TRANSLATION_CACHE.pop(next(iter(_TRANSLATION_CACHE)))
    _TRANSLATION_CACHE[source] = translated
    return translated


def _extract_meta_content(document: str, keys: tuple[str, ...]) -> str:
    lowered_keys = {k.lower() for k in keys}

    for tag in re.finditer(r"<meta\s+[^>]*>", document, flags=re.IGNORECASE):
        raw_tag = tag.group(0)
        attrs = dict(
            (m.group(1).lower(), html.unescape(m.group(2)).strip())
            for m in re.finditer(r"([a-zA-Z_:][\w:.-]*)\s*=\s*[\"']([^\"']*)[\"']", raw_tag)
        )
        key = (attrs.get("property") or attrs.get("name") or "").lower().strip()
        if key in lowered_keys:
            content = attrs.get("content", "").strip()
            if content:
                return content
    return ""


def _fetch_listing_preview_sync(url: str) -> dict[str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    with urllib.request.urlopen(request, timeout=8) as response:
        content_type = response.headers.get("Content-Type", "")
        charset = "utf-8"
        if "charset=" in content_type:
            charset = content_type.split("charset=", 1)[1].split(";", 1)[0].strip() or "utf-8"
        body = response.read().decode(charset, errors="ignore")

    title = _extract_meta_content(body, ("og:title", "twitter:title"))
    description = _extract_meta_content(
        body, ("og:description", "description", "twitter:description")
    )
    image = _extract_meta_content(body, ("og:image", "twitter:image"))

    return {
        "title": title,
        "description": description,
        "image": image,
    }


async def _get_cny_to_eur_rate() -> float:
    fallback = settings.cny_to_eur_rate if settings.cny_to_eur_rate > 0 else 0.13
    now = time.time()

    if _FX_CACHE["value"] > 0 and (now - _FX_CACHE["updated_at"] < _FX_CACHE_TTL_SECONDS):
        return _FX_CACHE["value"]

    async with _FX_LOCK:
        if _FX_CACHE["value"] > 0 and (
            time.time() - _FX_CACHE["updated_at"] < _FX_CACHE_TTL_SECONDS
        ):
            return _FX_CACHE["value"]

        try:
            xml_text = await asyncio.to_thread(_fetch_ecb_daily_xml)
            rate = _parse_cny_to_eur_from_ecb(xml_text)
            if rate and rate > 0:
                _FX_CACHE["value"] = rate
                _FX_CACHE["updated_at"] = time.time()
                return rate
        except Exception as e:
            log.warning("Failed to fetch live FX rate, using fallback: %s", e)

        _FX_CACHE["value"] = fallback
        _FX_CACHE["updated_at"] = time.time()
        return fallback


def _fetch_ecb_daily_xml() -> str:
    request = urllib.request.Request(
        "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/xml,text/xml,*/*"},
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        return response.read().decode("utf-8", errors="ignore")


def _parse_cny_to_eur_from_ecb(xml_text: str) -> float:
    root = ET.fromstring(xml_text)
    ns = {
        "gesmes": "http://www.gesmes.org/xml/2002-08-01",
        "e": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref",
    }
    cube_nodes = root.findall(".//e:Cube[@currency='CNY']", ns)
    if not cube_nodes:
        raise ValueError("CNY rate not present in ECB feed")
    cny_per_eur = float(cube_nodes[0].attrib.get("rate", "0"))
    if cny_per_eur <= 0:
        raise ValueError("Invalid CNY rate in ECB feed")
    return 1.0 / cny_per_eur


def _convert_goofish_short_url(url: str) -> str:
    if not url:
        return ""
    match = re.search(r"[?&]id=(\d+)", url)
    if not match:
        return url
    item_id = match.group(1)
    bfp_json = f'{{"id":{item_id}}}'
    encoded = quote(bfp_json)
    return (
        "https://pages.goofish.com/sharexy"
        "?loadingVisible=false&bft=item&bfs=idlepc.item&spm=a21ybx.item.0.0"
        f"&bfp={encoded}"
    )


def _build_superbuy_url(goofish_url: str) -> str:
    if not goofish_url:
        return ""
    encoded = quote(goofish_url, safe="")
    template = settings.superbuy_link_template.strip() or ""
    if "{url}" in template:
        return template.replace("{url}", encoded)
    return template or f"https://www.superbuy.com/en/page/buy/?url={encoded}"


def _first_non_empty(values: list[Any]) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _extract_listing_notification(payload: Any, content: str) -> ListingNotification | None:
    payload_dict = payload if isinstance(payload, dict) else {}
    raw_meta = payload_dict.get("meta")
    meta: dict[str, Any] = dict(raw_meta) if isinstance(raw_meta, dict) else {}

    # Support form-encoded fallback shape: meta_<field>=...
    for key, value in payload_dict.items():
        if not isinstance(key, str) or not key.startswith("meta_"):
            continue
        meta_key = key[5:]
        if not meta_key:
            continue
        if isinstance(value, str):
            stripped = value.strip()
            if (stripped.startswith("[") and stripped.endswith("]")) or (
                stripped.startswith("{") and stripped.endswith("}")
            ):
                try:
                    meta[meta_key] = json.loads(stripped)
                    continue
                except Exception:
                    pass
        meta[meta_key] = value

    def pick(*keys: str) -> str:
        values: list[Any] = []
        for key in keys:
            values.append(payload_dict.get(key))
            values.append(meta.get(key))
        return _first_non_empty(values)

    listing_title = pick("listing_title_en", "listing_title", "item_title", "product_title")
    reason = pick("reason_en", "reason", "ai_reason")
    description = pick(
        "listing_description_en", "description_en", "listing_description", "description"
    )
    price_raw = pick("price_cny_text", "listing_price_cny", "price", "listing_price")

    goofish_url = pick("goofish_pc_url", "listing_link_pc", "goofish_link", "link")
    goofish_short_url = pick("goofish_short_url", "listing_link_mobile", "mobile_link")
    superbuy_url = pick("superbuy_url")

    image_url = pick("listing_main_image", "main_image", "image")
    raw_images = payload_dict.get("listing_images")
    if not isinstance(raw_images, list):
        raw_images = meta.get("listing_images")
    image_urls = [str(u).strip() for u in (raw_images or []) if str(u).strip()]

    if not reason:
        reason = _extract_value_by_labels(content, ("Reason:", "AI Reason:", "原因:"))
    if not description:
        description = _extract_value_by_labels(content, ("Description:", "描述:"))
    if not price_raw:
        price_raw = _extract_value_by_labels(content, ("Price:", "价格:"))

    if not goofish_url:
        urls = _extract_urls(content)
        goofish_candidates = [u for u in urls if "goofish.com" in u]
        if goofish_candidates:
            goofish_url = goofish_candidates[-1]

    if not goofish_short_url and goofish_url:
        goofish_short_url = _convert_goofish_short_url(goofish_url)
    if not superbuy_url and goofish_url:
        superbuy_url = _build_superbuy_url(goofish_url)

    if not image_url and image_urls:
        image_url = image_urls[0]

    price_cny: float | None = None
    raw_price_value = payload_dict.get("price_cny_value")
    if raw_price_value is None:
        raw_price_value = meta.get("price_cny_value")
    if raw_price_value is not None:
        price_cny = _parse_cny_amount(raw_price_value)
    if price_cny is None:
        price_cny = _parse_cny_amount(price_raw)

    has_listing_signal = any(
        [
            listing_title,
            reason,
            description,
            price_raw,
            goofish_url,
            goofish_short_url,
            image_url,
            image_urls,
        ]
    )
    if not has_listing_signal:
        return None

    return ListingNotification(
        listing_title=listing_title,
        reason=reason,
        description=description,
        price_raw=price_raw,
        price_cny=price_cny,
        goofish_url=goofish_url,
        goofish_short_url=goofish_short_url,
        superbuy_url=superbuy_url,
        image_url=image_url,
        image_urls=image_urls,
    )


async def _enrich_listing_notification(listing: ListingNotification) -> ListingNotification:
    enriched = listing

    if listing.goofish_url and (
        not listing.image_url or not listing.description or not listing.listing_title
    ):
        try:
            preview = await asyncio.to_thread(_fetch_listing_preview_sync, listing.goofish_url)
        except (urllib.error.URLError, TimeoutError, ValueError):
            preview = {}
        except Exception:
            preview = {}

        preview_title = str(preview.get("title", "")).strip()
        preview_description = str(preview.get("description", "")).strip()
        preview_image = str(preview.get("image", "")).strip()

        image_urls = list(listing.image_urls)
        if preview_image and preview_image not in image_urls:
            image_urls.insert(0, preview_image)

        enriched = replace(
            enriched,
            listing_title=listing.listing_title or preview_title,
            description=listing.description or preview_description,
            image_url=listing.image_url or preview_image,
            image_urls=image_urls,
        )

    title_en = await _translate_to_english(enriched.listing_title)
    reason_en = await _translate_to_english(enriched.reason)
    description_en = await _translate_to_english(enriched.description)

    return replace(
        enriched,
        listing_title=title_en or enriched.listing_title,
        reason=reason_en or enriched.reason,
        description=description_en or enriched.description,
    )


async def _build_discord_embeds(title: str, content: str, raw: Any) -> list[discord.Embed]:
    listing = _extract_listing_notification(raw, content)
    if listing is None:
        fallback = discord.Embed(
            title=(title or "Goofish Monitor")[:256],
            description=_truncate(content or "(empty)", 4000),
            color=discord.Color.blurple(),
        )
        if raw is not None and raw != "":
            try:
                raw_text = json.dumps(raw, ensure_ascii=False, indent=2)
            except Exception:
                raw_text = str(raw)
            fallback.add_field(
                name="Raw", value=f"```json\n{_truncate(raw_text, 900)}\n```", inline=False
            )
        return [fallback]

    listing = await _enrich_listing_notification(listing)
    fx_rate = await _get_cny_to_eur_rate()

    listing_title = listing.listing_title or title or "Goofish listing alert"
    embed = discord.Embed(
        title=_truncate(listing_title, 256),
        description="Goofish listing matched your monitor criteria.",
        color=discord.Color.green(),
    )

    price_display = listing.price_raw or "N/A"
    if listing.price_cny is not None:
        price_display = f"¥{listing.price_cny:,.2f}"
        eur = listing.price_cny * fx_rate
        price_display += f" (~EUR {eur:,.2f})"
    embed.add_field(name="Price", value=price_display, inline=False)

    reason = listing.reason or _extract_value_by_labels(content, ("Reason:", "AI Reason:", "原因:"))
    embed.add_field(name="Why it is valid", value=_truncate(reason or "N/A", 1000), inline=False)

    if listing.description:
        embed.add_field(
            name="Description", value=_truncate(listing.description, 1000), inline=False
        )

    links: list[str] = []
    if listing.goofish_url:
        links.append(f"[Goofish (PC)]({listing.goofish_url})")
    if listing.goofish_short_url:
        links.append(f"[Goofish (Short)]({listing.goofish_short_url})")
    if listing.superbuy_url:
        links.append(f"[Superbuy (Converted)]({listing.superbuy_url})")
    if links:
        embed.add_field(name="Links", value="\n".join(links), inline=False)

    if listing.image_url:
        embed.set_image(url=listing.image_url)

    extra_embeds: list[discord.Embed] = []
    if listing.image_urls:
        deduped_images: list[str] = []
        for img in listing.image_urls:
            if img not in deduped_images:
                deduped_images.append(img)

        # Keep total embeds <= 10. We send up to 4 listing images.
        for idx, img in enumerate(deduped_images[:4]):
            if idx == 0 and listing.image_url:
                continue
            image_embed = discord.Embed(color=discord.Color.dark_teal())
            image_embed.set_image(url=img)
            image_embed.set_footer(text=f"Listing image {idx + 1}")
            extra_embeds.append(image_embed)

    return [embed, *extra_embeds]


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

    embeds = await _build_discord_embeds(title, content, raw)

    try:
        await user.send(embeds=embeds)
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

        payload: Any
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

        title, content = _extract_title_content(payload)

        if _should_drop_notification(title, content):
            log.info("Dropped auth-expired webhook notification: %s", _truncate(content, 200))
            return web.json_response({"ok": True, "dropped": True})

        asyncio.create_task(_send_discord_dm(self.bot, title, content, payload))
        return web.json_response({"ok": True})
