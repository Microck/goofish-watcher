import logging
from typing import Dict
from core.notifications import NotificationClient

log = logging.getLogger(__name__)


class TelegramClient(NotificationClient):
    def __init__(self):
        from config import settings

        super().__init__(enabled=bool(settings.telegram_bot_token and settings.telegram_chat_id))
        self._bot_token = settings.telegram_bot_token
        self._chat_id = settings.telegram_chat_id

    async def send(self, product_data: Dict, reason: str) -> bool:
        if not self.is_enabled():
            return False

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                msg = self._format_message(product_data, reason)
                text = f"📦 <b>{msg['title']}</b>\n\n💰 {msg['price']}\n\n{msg['reason']}\n\n🔗 {msg['link']}"

                url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
                payload = {
                    "chat_id": self._chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                }

                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        log.info("Telegram notification sent successfully")
                        return True
                    else:
                        log.error(f"Telegram notification failed: {resp.status}")
                        return False
        except Exception as e:
            log.error(f"Telegram notification error: {e}", exc_info=True)
            return False
