import logging
from typing import Dict
from core.notifications import NotificationClient

log = logging.getLogger(__name__)


class BarkClient(NotificationClient):
    def __init__(self):
        from config import settings

        super().__init__(enabled=bool(settings.bark_url))
        self._bark_url = settings.bark_url

    async def send(self, product_data: Dict, reason: str) -> bool:
        if not self.is_enabled():
            return False

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                msg = self._format_message(product_data, reason)
                title = msg["title"]
                body = f"{msg['price']}\n\n{msg['reason']}\n\n{msg['link']}"

                # Bark URL format: https://api.day.app/your_key/title/body
                url = f"{self._bark_url}/{title}/{body}"

                async with session.get(url) as resp:
                    if resp.status == 200:
                        log.info("Bark notification sent successfully")
                        return True
                    else:
                        log.error(f"Bark notification failed: {resp.status}")
                        return False
        except Exception as e:
            log.error(f"Bark notification error: {e}", exc_info=True)
            return False
