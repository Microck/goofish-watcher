import json
import logging
from typing import Dict
from core.notifications import NotificationClient

log = logging.getLogger(__name__)


class WebhookClient(NotificationClient):
    def __init__(self):
        from config import settings

        super().__init__(enabled=bool(settings.webhook_url))
        self._url = settings.webhook_url
        self._method = settings.webhook_method.upper()
        self._headers = json.loads(settings.webhook_headers) if settings.webhook_headers else {}
        self._body_template = settings.webhook_body
        self._content_type = settings.webhook_content_type.upper()

    async def send(self, product_data: Dict, reason: str) -> bool:
        if not self.is_enabled():
            return False

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                msg = self._format_message(product_data, reason)

                # Replace placeholders in body template
                body = self._body_template
                if body:
                    body = body.replace("{{title}}", msg["title"])
                    body = content.replace(
                        "{{content}}", f"{msg['price']}\n{msg['reason']}\n{msg['link']}"
                    )

                headers = dict(self._headers)
                if self._content_type == "JSON":
                    headers["Content-Type"] = "application/json"
                    payload = json.loads(body) if body else msg
                else:
                    headers["Content-Type"] = "application/x-www-form-urlencoded"
                    payload = body

                if self._method == "POST":
                    async with session.post(self._url, json=payload, headers=headers) as resp:
                        success = resp.status in (200, 201, 202)
                else:
                    async with session.get(self._url, params=payload, headers=headers) as resp:
                        success = resp.status in (200, 201, 202)

                if success:
                    log.info("Webhook notification sent successfully")
                    return True
                else:
                    log.error(f"Webhook notification failed: {resp.status}")
                    return False
        except Exception as e:
            log.error(f"Webhook notification error: {e}", exc_info=True)
            return False
