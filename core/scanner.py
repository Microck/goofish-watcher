import asyncio
import json
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urljoin

from playwright.async_api import async_playwright, BrowserContext

from config import settings

log = logging.getLogger(__name__)

SEARCH_URL = "https://www.goofish.com/search"
BASE_URL = "https://www.goofish.com"


def _detect_chrome_channel() -> str | None:
    """Return 'chrome' if system Chrome is available, None otherwise (use bundled Chromium)."""
    if os.environ.get("USE_BUNDLED_CHROMIUM"):
        return None
    chrome_paths = [
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
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


class GoofishClient:
    def __init__(self, cookies_path: str | None = None):
        self.cookies_path = cookies_path or settings.goofish_cookies_json_path
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

            self._context = await self._playwright.chromium.launch_persistent_context(
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

            cookies = self._load_cookies()
            if cookies:
                await self._context.add_cookies(cookies)
                log.info(f"Loaded {len(cookies)} auth cookies")

            page = await self._context.new_page()
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            log.info("Browser warmed up")

            self._profile_initialized = True
            return self._context

    def _load_cookies(self) -> list[dict]:
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

            url = f"{SEARCH_URL}?q={quote(keyword)}"
            if page > 1:
                url += f"&page={page}"

            log.info(f"Searching: {url}")

            await browser_page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(1)
            await browser_page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await browser_page.wait_for_selector('a[href*="/item?id="]', timeout=15000)
            await asyncio.sleep(1)

            listings_data = await browser_page.evaluate("""
                () => {
                    const results = [];
                    const links = document.querySelectorAll('a[href*="/item?id="]');
                    
                    for (const link of links) {
                        const href = link.getAttribute('href');
                        const idMatch = href.match(/id=(\d+)/);
                        if (!idMatch) continue;
                        
                        const itemId = idMatch[1];
                        const text = link.innerText || link.textContent || '';
                        
                        const priceMatch = text.match(/¥\s*([\d,.]+)/);
                        const price = priceMatch ? priceMatch[1].replace(',', '') : '0';
                        
                        const img = link.querySelector('img');
                        const imgSrc = img ? (img.src || img.dataset.src || '') : '';
                        
                        let title = text.split('¥')[0].trim();
                        if (title.length > 100) {
                            title = title.substring(0, 100);
                        }
                        
                        const locationMatch = text.match(/(\d+人想要)?\s*([\u4e00-\u9fa5]{2,})\s*$/);
                        const location = locationMatch ? locationMatch[2] : '';
                        
                        results.push({
                            id: itemId,
                            title: title,
                            price: parseFloat(price) || 0,
                            imageUrl: imgSrc,
                            location: location,
                            href: href,
                        });
                    }
                    
                    const seen = new Set();
                    return results.filter(r => {
                        if (seen.has(r.id)) return false;
                        seen.add(r.id);
                        return true;
                    });
                }
            """)

            log.info(f"Found {len(listings_data)} raw listings")

            if not listings_data:
                screenshot_path = Path("debug_scan_empty.png")
                await browser_page.screenshot(path=str(screenshot_path))
                page_url = browser_page.url
                log.warning(f"0 listings found! URL: {page_url}, screenshot saved to {screenshot_path}")

            listings = []
            for item in listings_data[:page_size]:
                listing = RawListing(
                    id=str(item["id"]),
                    title=item["title"],
                    price=float(item["price"]),
                    image_url=item.get("imageUrl", ""),
                    seller_id="",
                    seller_name="",
                    location=item.get("location", ""),
                    post_time=None,
                    detail_url=urljoin(BASE_URL, item["href"]),
                )
                listings.append(listing)

            return listings

        except Exception as e:
            log.error(f"Search failed: {e}", exc_info=True)
            return []

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
