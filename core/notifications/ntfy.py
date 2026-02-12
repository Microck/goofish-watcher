import logging
from typing import Dict
from core.notifications import NotificationClient

log = logging.getLogger(__name__)


class NtfyClient(NotificationClient):
    def __init__(self):
        from config import settings

        super().__init__(enabled=bool(settings.ntfy_topic_url))
        self._topic_url = settings.ntfy_topic_url

    async def send(self, product_data: Dict, reason: str) -> bool:
        if not self.is_enabled():
            return False

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                msg = self._format_message(product_data, reason)
                payload = f"{msg['title']}\n{msg['reason']}\n\n{msg['link']}"

                async with session.post(self._topic_url, data=payload.encode()) as resp:
                    if resp.status in (200, 201):
                        log.info(f"Ntfy notification sent successfully")
                        return True
                    else:
                        log.error(f"Ntfy notification failed: {resp.status}")
                        return False
        except Exception as e:
            log.error(f"Ntfy notification error: {e}", exc_info=True)
            return False
