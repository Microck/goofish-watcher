import asyncio
import logging
from typing import Dict, List
from core.notifications import NotificationClient
from core.notifications.ntfy import NtfyClient
from core.notifications.telegram import TelegramClient
from core.notifications.bark import BarkClient
from core.notifications.webhook import WebhookClient

log = logging.getLogger(__name__)


class NotificationManager:
    def __init__(self):
        self.clients: List[NotificationClient] = [
            NtfyClient(),
            TelegramClient(),
            BarkClient(),
            WebhookClient(),
        ]
        self._enabled_clients = [c for c in self.clients if c.is_enabled()]
        log.info(
            f"NotificationManager initialized with {len(self._enabled_clients)} enabled clients"
        )

    async def send_to_all(self, product_data: Dict, reason: str) -> Dict[str, bool]:
        if not self._enabled_clients:
            log.debug("No notification clients enabled")
            return {}

        tasks = [client.send(product_data, reason) for client in self._enabled_clients]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        result_dict = {}
        for i, result in enumerate(results):
            client_name = self._enabled_clients[i].__class__.__name__
            if isinstance(result, Exception):
                log.error(f"{client_name} failed: {result}")
                result_dict[client_name] = False
            else:
                result_dict[client_name] = result

        return result_dict

    def get_enabled_channels(self) -> List[str]:
        return [c.__class__.__name__ for c in self._enabled_clients]


notification_manager = NotificationManager()
