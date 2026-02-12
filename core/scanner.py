import asyncio
import json
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from playwright.async_api import async_playwright, BrowserContext, Response

from config import settings

log = logging.getLogger(__name__)

SEARCH_URL = "https://www.goofish.com/search"
BASE_URL = "https://www.goofish.com"
API_SEARCH_URL = "h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search"
API_DETAIL_URL = "h5api.m.goofish.com/h5/mtop.taobao.idle.pc.detail"
API_RATINGS_URL = "h5api.m.goofish.com/h5/mtop.idle.web.trade.rate.list"


def _detect_chrome_channel() -> str | None:
    if os.environ.get("USE_BUNDLED_CHROMIUM"):
        return None
    chrome_paths = [
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for path in chrome_paths:
        if path and Path(path).exists():
            return "chrome"
    return None


@dataclass
class RawListing:
    id: str
    title: str
    price: float
    image_url: str
    seller_id: str
    seller_name: str
    location: str
    post_time: str | None
    detail_url: str
    original_price: str | None = None
    wants_count: int | None = None
    tags: list[str] = None


class GoofishClient:
    def __init__(self, cookies_path: Optional[str] = None):
        self.cookies_path = (
            cookies_path or str(settings.goofish_cookies_json_path)
            if settings.goofish_cookies_json_path
            else None
        )
        self._playwright = None
        self._context: BrowserContext | None = None
        self._lock = asyncio.Lock()
        self._profile_initialized = False

    async def _ensure_browser(self) -> BrowserContext:
        if self._context:
            return self._context

        async with self._lock:
            if self._context:
                return self._context

            self._playwright = await async_playwright().start()

            profile_dir = Path(self.cookies_path).parent / "chrome_profile"
            profile_dir.mkdir(parents=True, exist_ok=True)

            chrome_channel = _detect_chrome_channel()
            log.info(f"Using browser channel: {chrome_channel or 'bundled chromium'}")

            self._context = (
                await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=True,
                    channel=chrome_channel,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                    ],
                    viewport={"width": 1920, "height": 1080},
                    locale="zh-CN",
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                )
                if chrome_channel
                else None
            )

            cookies = self._load_cookies()
            if cookies and self._context:
                await self._context.add_cookies(cookies)
                log.info(f"Loaded {len(cookies)} auth cookies")

            page = await self._context.new_page()
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            log.info("Browser warmed up")

            self._profile_initialized = True
            return self._context

    def _load_cookies(self) -> list:
        if not self.cookies_path:
            return []

        path = Path(self.cookies_path)
        if not path.exists():
            log.warning(f"Cookies file not found: {path}")
            return []

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            cookies = []

            for c in data:
                cookie = {
                    "name": c.get("name"),
                    "value": c.get("value"),
                    "domain": c.get("domain", ".goofish.com"),
                    "path": c.get("path", "/"),
                    "sameSite": "Lax",
                }
                if cookie["name"] and cookie["value"]:
                    cookies.append(cookie)

            log.info(f"Loaded {len(cookies)} cookies from {path}")
            return cookies
        except Exception as e:
            log.error(f"Failed to load cookies: {e}")
            return []

    async def close(self) -> None:
        if self._context:
            await self._context.close()
            self._context = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def export_cookies(self, output_path: str | None = None) -> list[dict]:
        context = await self._ensure_browser()
        cookies = await context.cookies()
        goofish_cookies = [c for c in cookies if "goofish" in c.get("domain", "")]

        if output_path:
            Path(output_path).write_text(
                json.dumps(goofish_cookies, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            log.info(f"Exported {len(goofish_cookies)} cookies to {output_path}")

        return goofish_cookies

    async def backup_cookies(self) -> None:
        backup_path = Path(self.cookies_path).parent / "cookies_backup.json"
        await self.export_cookies(str(backup_path))

    async def refresh_cookies(self) -> None:
        cookies = await self.export_cookies()
        if cookies and self.cookies_path:
            Path(self.cookies_path).write_text(
                json.dumps(cookies, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            log.info(f"Refreshed cookies.json with {len(cookies)} current cookies")

    async def keep_alive(self) -> bool:
        try:
            context = await self._ensure_browser()
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20000)
            log.debug("Session keep-alive: visited homepage")
            return True
        except Exception as e:
            log.warning(f"Keep-alive failed: {e}")
            return False

    async def search(self, keyword: str, page: int = 1, page_size: int = 50) -> list[RawListing]:
        try:
            context = await self._ensure_browser()
            browser_page = context.pages[0] if context.pages else await context.new_page()

            search_results = []

            async def handle_response(response: Response):
                if API_SEARCH_URL in response.url:
                    try:
                        json_data = await response.json()
                        from core.parsers import parse_search_results_json

                        listings = await parse_search_results_json(json_data)
                        search_results.extend(listings)
                        log.info(f"API拦截: 捕获到 {len(listings)} 条商品数据")
                    except Exception as e:
                        log.error(f"Failed to parse API response: {e}", exc_info=True)

            browser_page.on("response", handle_response)

            params = {"q": keyword}
            if page > 1:
                params["page"] = str(page)

            log.info(f"Searching with API拦截: keyword={keyword}, page={page}")

            await browser_page.goto(
                f"{SEARCH_URL}?{urlencode(params)}", wait_until="domcontentloaded", timeout=30000
            )
            await asyncio.sleep(3)

            if not search_results:
                screenshot_path = Path("debug_scan_empty.png")
                await browser_page.screenshot(path=str(screenshot_path))
                page_url = browser_page.url
                log.warning(
                    f"0 listings found! URL: {page_url}, screenshot saved to {screenshot_path}"
                )

            listings = []
            for item in search_results[:page_size]:
                listing = RawListing(
                    id=item.id,
                    title=item.title,
                    price=item.price,
                    image_url=item.image_url,
                    seller_id=item.seller_id,
                    seller_name=item.seller_name,
                    location=item.location,
                    post_time=datetime.fromtimestamp(item.post_time).strftime("%Y-%m-%d %H:%M")
                    if item.post_time
                    else None,
                    detail_url=item.detail_url,
                    original_price=item.original_price,
                    wants_count=item.wants_count,
                    tags=item.tags or [],
                )
                listings.append(listing)

            return listings

        except Exception as e:
            log.error(f"Search failed: {e}", exc_info=True)
            return []

    async def get_listing_detail(self, listing_id: str) -> dict:
        try:
            context = await self._ensure_browser()
            page = context.pages[0] if context.pages else await context.new_page()

            detail_result = {}

            async def handle_response(response: Response):
                if API_DETAIL_URL in response.url:
                    try:
                        json_data = await response.json()
                        from core.parsers import parse_detail_json

                        detail = await parse_detail_json(json_data)
                        detail_result.update(detail)
                        log.info(f"API拦截: 获取商品详情 {listing_id}")
                    except Exception as e:
                        log.error(f"Failed to parse detail API response: {e}", exc_info=True)

            page.on("response", handle_response)

            detail_url = f"{BASE_URL}/item?id={listing_id}"
            await page.goto(detail_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            return detail_result

        except Exception as e:
            log.error(f"Get listing detail failed: {e}", exc_info=True)
            return {}

    async def get_seller_reputation(self, seller_id: str) -> dict:
        try:
            context = await self._ensure_browser()
            page = context.pages[0] if context.pages else await context.new_page()

            reputation_result = {"ratings": {}, "head": {}}

            async def handle_response(response: Response):
                if API_RATINGS_URL in response.url:
                    try:
                        json_data = await response.json()
                        from core.parsers import parse_ratings_json

                        ratings = await parse_ratings_json(json_data)
                        reputation_result["ratings"] = ratings
                        log.info(f"API拦截: 获取卖家 {seller_id} 评价数据")
                    except Exception as e:
                        log.error(f"Failed to parse ratings API response: {e}", exc_info=True)
                elif "mtop.idle.web.user.page.head" in response.url:
                    try:
                        json_data = await response.json()
                        from core.parsers import parse_user_head_json

                        head = await parse_user_head_json(json_data)
                        reputation_result["head"] = head
                        log.info(f"API拦截: 获取卖家 {seller_id} 头部信息")
                    except Exception as e:
                        log.error(f"Failed to parse user head API response: {e}", exc_info=True)

            page.on("response", handle_response)

            await page.goto(
                f"{BASE_URL}/personal?userId={seller_id}",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await asyncio.sleep(3)

            from core.parsers import calculate_reputation

            return calculate_reputation(
                reputation_result.get("ratings", {}), reputation_result.get("head", {})
            )

        except Exception as e:
            log.error(f"Get seller reputation failed: {e}", exc_info=True)
            return {
                "registration_days": 0,
                "registration_text": "未知",
                "seller_total": 0,
                "seller_rate": 0,
                "total_transactions": 0,
                "reputation_score": 0,
            }

    async def check_auth(self) -> bool:
        try:
            context = await self._ensure_browser()
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20000)

            content = await page.content()
            if "punish" in content.lower() or "captcha" in content.lower():
                return False

            return True
        except Exception as e:
            log.error(f"Auth check failed: {e}")
            return False


goofish_client = GoofishClient()
