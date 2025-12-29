import base64
import json
import logging
from dataclasses import dataclass

import httpx

from config import settings
from core.parser import Listing
from db.models import Query

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI that determines if a product listing is relevant to a search query.
Analyze the listing title, price, images, and context to determine relevance.
You MUST respond with valid JSON only, no markdown or extra text.
Response format: {"relevant": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}"""


@dataclass
class VerificationResult:
    relevant: bool
    confidence: float
    reason: str


class AIVerifier:
    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if not self._client:
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {settings.nvidia_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _fetch_image_base64(self, url: str) -> str | None:
        try:
            client = await self._get_client()
            resp = await client.get(url, timeout=30.0)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "image/jpeg")
            base64_data = base64.b64encode(resp.content).decode("utf-8")
            return f"data:{content_type};base64,{base64_data}"
        except Exception as e:
            log.warning(f"Failed to fetch image {url}: {e}")
            return None

    async def verify(
        self,
        listing: Listing,
        query: Query,
        image_urls: list[str] | None = None,
    ) -> VerificationResult | None:
        if not query.ai_enabled:
            return VerificationResult(relevant=True, confidence=1.0, reason="AI disabled")

        client = await self._get_client()

        description_part = ""
        if query.description:
            description_part = f"\nUser is looking for: {query.description}"

        user_prompt = f"""Search query: "{query.keyword}"{description_part}
Include terms: {query.include_terms or "none"}
Exclude terms: {query.exclude_terms or "none"}
Price range: {query.min_price or "any"} - {query.max_price or "any"}

Listing:
- Title: {listing.title}
- Price: ¥{listing.price}
- Location: {listing.location}

Is this listing relevant to the search query?"""

        use_vision = bool(image_urls)
        model = settings.nvidia_vision_model if use_vision else settings.nvidia_model

        if use_vision and image_urls:
            content_parts: list[dict] = [{"type": "text", "text": user_prompt}]
            
            for url in image_urls[:3]:
                image_data = await self._fetch_image_base64(url)
                if image_data:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": image_data}
                    })
            
            if len(content_parts) == 1:
                use_vision = False
                model = settings.nvidia_model
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
            else:
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": content_parts},
                ]
        else:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 200,
        }

        try:
            resp = await client.post(settings.nvidia_endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()

            content = data["choices"][0]["message"]["content"]
            result = self._parse_response(content)
            return result

        except httpx.HTTPError as e:
            log.error(f"AI verification request failed: {e}")
            return None
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            log.error(f"Failed to parse AI response: {e}")
            return None

    def _parse_response(self, content: str) -> VerificationResult:
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        data = json.loads(content)
        return VerificationResult(
            relevant=bool(data.get("relevant", False)),
            confidence=float(data.get("confidence", 0.0)),
            reason=str(data.get("reason", "")),
        )


ai_verifier = AIVerifier()
