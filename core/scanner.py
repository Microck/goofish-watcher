import asyncio
import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, cast

from playwright.async_api import Browser, BrowserContext, async_playwright

from config import settings

log = logging.getLogger(__name__)

BASE_URL = "https://www.goofish.com"
SEARCH_URL = "https://www.goofish.com/search"


def _normalize_same_site(value: str | None) -> str:
    if not value:
        return "Lax"
    v = value.strip().lower()
    if v in {"none", "no_restriction", "no-restriction", "no restriction"}:
        return "None"
    if v == "strict":
        return "Strict"
    return "Lax"


def _find_playwright_full_chromium_executable() -> str | None:
    """Prefer full Chromium binary over headless_shell when available."""

    try:
        base = Path.home() / ".cache" / "ms-playwright"
        candidates = sorted(base.glob("chromium-*/chrome-linux/chrome"))
        if not candidates:
            return None
        return str(candidates[-1])
    except Exception:
        return None


def _detect_chrome_channel() -> str | None:
    if os.environ.get("USE_BUNDLED_CHROMIUM"):
        return None

    chrome_paths = [
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        r"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for path in chrome_paths:
        if path and Path(path).exists():
            return "chrome"
    return None


class GoofishClient:
    def __init__(self) -> None:
        self.cookies_path = str(settings.goofish_cookies_json_path)
        self._playwright = None
        self._context: BrowserContext | None = None
        self._lock = asyncio.Lock()

        # QR login resources (kept separate from main persistent context)
        self._qr_playwright = None
        self._qr_browser: Browser | None = None
        self._qr_context: BrowserContext | None = None
        self._qr_login_page = None
        self._qr_lock = asyncio.Lock()

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

            user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]

            if chrome_channel:
                self._context = await self._playwright.chromium.launch_persistent_context(
                    str(profile_dir),
                    channel=chrome_channel,
                    headless=True,
                    args=args,
                    viewport={"width": 1920, "height": 1080},
                    locale="zh-CN",
                    user_agent=user_agent,
                )
            else:
                self._context = await self._playwright.chromium.launch_persistent_context(
                    str(profile_dir),
                    headless=True,
                    args=args,
                    viewport={"width": 1920, "height": 1080},
                    locale="zh-CN",
                    user_agent=user_agent,
                )

            cookies = self._load_cookies()
            if cookies:
                await self._context.add_cookies(cookies)  # type: ignore[arg-type]
                log.info(f"Loaded {len(cookies)} auth cookies")

            # Warm up once to reduce first-request flakiness.
            page = await self._context.new_page()
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            return self._context

    def _load_cookies(self) -> list[dict[str, Any]]:
        path = Path(self.cookies_path)
        if not path.exists():
            return []

        try:
            data = json.loads(path.read_text(encoding="utf-8"))

            # Support Cookie-Editor export format: {"url": "...", "cookies": [...]}
            if isinstance(data, dict) and isinstance(data.get("cookies"), list):
                data = data["cookies"]

            if not isinstance(data, list):
                log.warning(f"Unsupported cookies format in {path}")
                return []

            cookies: list[dict[str, Any]] = []
            for c in data:
                name = c.get("name")
                value = c.get("value")
                if not isinstance(name, str) or not name:
                    continue
                if not isinstance(value, str) or not value:
                    continue

                domain = c.get("domain")
                path = c.get("path")

                cookie: dict[str, Any] = {
                    "name": name,
                    "value": value,
                    "domain": domain if isinstance(domain, str) and domain else ".goofish.com",
                    "path": path if isinstance(path, str) and path else "/",
                    "httpOnly": bool(c.get("httpOnly", False)),
                    "secure": bool(c.get("secure", True)),
                    "sameSite": _normalize_same_site(c.get("sameSite")),
                }

                # Cookie-Editor uses `expirationDate` (seconds) for persistent cookies
                if c.get("session") is False and c.get("expirationDate"):
                    try:
                        cookie["expires"] = float(c["expirationDate"])
                    except Exception:
                        pass

                cookies.append(cookie)

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

        if self._qr_login_page and not self._qr_login_page.is_closed():
            try:
                await self._qr_login_page.close()
            except Exception:
                pass
        self._qr_login_page = None

        if self._qr_context:
            try:
                await self._qr_context.close()
            except Exception:
                pass
        self._qr_context = None

        if self._qr_browser:
            try:
                await self._qr_browser.close()
            except Exception:
                pass
        self._qr_browser = None

        if self._qr_playwright:
            try:
                await self._qr_playwright.stop()
            except Exception:
                pass
        self._qr_playwright = None

    async def export_storage_state(self, output_path: str) -> Any:
        """Export Playwright storage_state (cookies + origins) for ai-goofish-monitor."""

        context = await self._ensure_browser()

        # Ensure at least one navigation so storage state is populated.
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
        except Exception:
            pass

        state = cast(dict[str, Any], await context.storage_state())
        Path(output_path).write_text(
            json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return state

    async def check_auth(self) -> bool:
        try:
            context = await self._ensure_browser()
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(3)

            login_markers = [
                "短信登录",
                "密码登录",
                "手机扫码安全登录",
                "闲鱼APP扫码",
                "立即登录",
            ]

            for frame in page.frames:
                try:
                    if "passport.goofish.com" in (frame.url or ""):
                        return False
                except Exception:
                    pass

                try:
                    text = await frame.inner_text("body")
                except Exception:
                    continue

                lowered = text.lower()
                if "punish" in lowered or "captcha" in lowered:
                    return False
                if "非法访问" in text:
                    return False
                if any(m in text for m in login_markers):
                    return False

            return True
        except Exception as e:
            log.error(f"Auth check failed: {e}")
            return False

    async def qr_login_start(self, keyword: str = "iphone") -> dict:
        """Start QR login and return QR screenshot bytes (PNG)."""

        try:
            async with self._qr_lock:
                # Tear down any previous QR session
                if self._qr_login_page and not self._qr_login_page.is_closed():
                    try:
                        await self._qr_login_page.close()
                    except Exception:
                        pass
                self._qr_login_page = None

                if self._qr_context:
                    try:
                        await self._qr_context.close()
                    except Exception:
                        pass
                self._qr_context = None

                if self._qr_browser:
                    try:
                        await self._qr_browser.close()
                    except Exception:
                        pass
                self._qr_browser = None

                if not self._qr_playwright:
                    self._qr_playwright = await async_playwright().start()

                chrome_channel = _detect_chrome_channel()
                chromium_exec = _find_playwright_full_chromium_executable()

                ua = (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )

                browser_args = [
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-gpu",
                    "--disable-gpu-compositing",
                    "--disable-software-rasterizer",
                    "--disable-accelerated-2d-canvas",
                    "--disable-features=VizDisplayCompositor",
                    "--disable-site-isolation-trials",
                    "--renderer-process-limit=1",
                    "--no-zygote",
                ]

                launch_kwargs: dict = {
                    "headless": True,
                    "args": browser_args,
                }
                if chromium_exec:
                    launch_kwargs["executable_path"] = chromium_exec
                elif chrome_channel:
                    launch_kwargs["channel"] = chrome_channel

                self._qr_browser = await self._qr_playwright.chromium.launch(**launch_kwargs)
                self._qr_context = await self._qr_browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    locale="zh-CN",
                    user_agent=ua,
                )

                page = await self._qr_context.new_page()
                self._qr_login_page = page

                await page.add_init_script(
                    """
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'languages',
                        { get: () => ['zh-CN', 'zh', 'en'] });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
                    window.navigator.chrome = { runtime: {} };
                    """
                )

            url = f"{SEARCH_URL}?q={keyword}"
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait for the login UI to appear.
            body_text = ""
            for _ in range(20):
                await asyncio.sleep(1)
                if page.is_closed():
                    return {"success": False, "qr_png": None, "error": "QR login page closed"}
                try:
                    body_text = await page.inner_text("body")
                except Exception:
                    continue
                if "非法访问" in body_text:
                    return {
                        "success": False,
                        "qr_png": None,
                        "error": "Blocked by Goofish: 非法访问",
                    }
                if (
                    "手机扫码安全登录" in body_text
                    or "闲鱼APP扫码" in body_text
                    or "短信登录" in body_text
                ):
                    break

            dialog = None
            try:
                dialog_candidates = await page.query_selector_all(
                    '[role="dialog"], [class*="modal"], [class*="login"]'
                )
                best = None
                best_area = 0.0
                for el in dialog_candidates:
                    box = await el.bounding_box()
                    if not box:
                        continue
                    area = float(box.get("width", 0)) * float(box.get("height", 0))
                    if area > best_area:
                        best = el
                        best_area = area
                if best and best_area >= 500 * 300:
                    dialog = best
            except Exception:
                dialog = None

            if not dialog:
                dialog = await page.query_selector(
                    '[role="dialog"], [class*="modal"], [class*="login"]'
                )
            if not dialog:
                return {
                    "success": False,
                    "qr_png": None,
                    "error": "Login dialog not found (maybe already logged in?)",
                }

            qr_png = None
            try:
                candidates = await dialog.query_selector_all("svg, canvas, img")
                best = None
                best_area = 0.0
                for el in candidates:
                    box = await el.bounding_box()
                    if not box:
                        continue
                    w = float(box.get("width", 0))
                    h = float(box.get("height", 0))
                    if w < 150 or h < 150:
                        continue
                    ratio = w / h if h else 0
                    if ratio < 0.8 or ratio > 1.25:
                        continue
                    area = w * h
                    if area > best_area:
                        best = el
                        best_area = area
                if best and best_area >= 200 * 200:
                    qr_png = await best.screenshot(type="png")
            except Exception:
                qr_png = None

            if not qr_png:
                qr_png = await dialog.screenshot(type="png")

            return {"success": True, "qr_png": qr_png, "error": None}
        except Exception as e:
            log.error(f"QR login start failed: {e}", exc_info=True)
            return {"success": False, "qr_png": None, "error": str(e)}

    async def qr_login_wait(self, timeout: int = 120) -> dict:
        page = self._qr_login_page
        if not page or not self._qr_context:
            return {"success": False, "error": "No active QR login session"}

        try:
            before = await self._qr_context.cookies()
            before_names = {c.get("name") for c in before if c.get("name")}

            strong_auth_cookie_names = {"tracknick", "_nk_", "lgc", "unb"}
            start_time = time.time()

            while time.time() - start_time < timeout:
                await asyncio.sleep(2)
                if page.is_closed():
                    return {"success": False, "error": "QR login page closed"}

                try:
                    text = await page.inner_text("body")
                except Exception:
                    continue

                if "非法访问" in text:
                    return {"success": False, "error": "Blocked by Goofish: 非法访问"}

                cookies_now = await self._qr_context.cookies()
                now_names = {c.get("name") for c in cookies_now if c.get("name")}
                gained_names = now_names - before_names

                login_modal_visible = (
                    "短信登录" in text or "手机扫码" in text or "闲鱼APP扫码" in text
                )
                strong_auth = bool(now_names & strong_auth_cookie_names)
                meaningful_cookie_change = bool(gained_names) or (
                    len(cookies_now) > len(before) + 3
                )

                if strong_auth or (not login_modal_visible and meaningful_cookie_change):
                    # Verify by reloading homepage and checking rendered text.
                    try:
                        await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(3)
                        verify_text = await page.inner_text("body")
                    except Exception:
                        verify_text = ""

                    if (
                        "短信登录" in verify_text
                        or "手机扫码安全登录" in verify_text
                        or "闲鱼APP扫码" in verify_text
                    ):
                        return {
                            "success": False,
                            "error": "QR scan completed but session is still not logged in",
                        }

                    try:
                        Path(self.cookies_path).write_text(
                            json.dumps(cookies_now, indent=2, ensure_ascii=False),
                            encoding="utf-8",
                        )
                        log.info(f"Saved {len(cookies_now)} cookies to {self.cookies_path}")
                    except Exception as e:
                        log.warning(f"Failed to save cookies after QR login: {e}")

                    # Reset main context so next usage reloads cookies.
                    if self._context:
                        try:
                            await self._context.close()
                        except Exception:
                            pass
                        self._context = None

                    return {"success": True, "error": None}

            return {"success": False, "error": "Login timed out"}
        except Exception as e:
            log.error(f"QR login wait failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
        finally:
            try:
                await page.close()
            except Exception:
                pass
            self._qr_login_page = None

            if self._qr_context:
                try:
                    await self._qr_context.close()
                except Exception:
                    pass
                self._qr_context = None

            if self._qr_browser:
                try:
                    await self._qr_browser.close()
                except Exception:
                    pass
                self._qr_browser = None


goofish_client = GoofishClient()
