from abc import ABC, abstractmethod
from typing import Dict


class NotificationClient(ABC):
    def __init__(self, enabled: bool = False):
        self._enabled = enabled

    def is_enabled(self) -> bool:
        return self._enabled

    @abstractmethod
    async def send(self, product_data: Dict, reason: str) -> bool:
        pass

    def _format_message(self, product_data: Dict, reason: str) -> Dict[str, str]:
        title = product_data.get("title", "N/A")
        price = product_data.get("price_str", "N/A")
        link = product_data.get("detail_url", "#")

        return {"title": title, "price": price, "link": link, "reason": reason}
