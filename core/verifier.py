import json
import logging
from dataclasses import dataclass

import httpx

from config import settings
from core.parser import Listing
from db.models import Query

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI that determines if a product listing is relevant to a search query.
Analyze the listing title, price, and context to determine relevance.
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
                timeout=60.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def verify(self, listing: Listing, query: Query) -> VerificationResult | None:
        if not query.ai_enabled:
            return VerificationResult(relevant=True, confidence=1.0, reason="AI disabled")

        client = await self._get_client()

        user_prompt = f"""Search query: "{query.keyword}"
Include terms: {query.include_terms or "none"}
Exclude terms: {query.exclude_terms or "none"}
Price range: {query.min_price or "any"} - {query.max_price or "any"}

Listing:
- Title: {listing.title}
- Price: ¥{listing.price}
- Location: {listing.location}

Is this listing relevant to the search query?"""

        payload = {
            "model": settings.nvidia_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
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
