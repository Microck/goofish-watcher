import base64
import logging
from dataclasses import dataclass
from typing import Any

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
        self._client: Any = None

    def _get_client(self) -> Any:
        if not self._client:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(
                    api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url,
                )
                log.info(f"Initialized OpenAI client with model: {settings.openai_model_name}")
            except ImportError:
                log.warning("OpenAI package not installed, falling back to NVIDIA NIM")
                try:
                    from openai import AsyncOpenAI

                    self._client = AsyncOpenAI(
                        api_key=settings.nvidia_api_key,
                        base_url=settings.nvidia_endpoint,
                    )
                    log.info(
                        f"Initialized fallback client with NVIDIA model: {settings.nvidia_model}"
                    )
                except ImportError:
                    log.error("Neither openai nor httpx available for AI verification")
                    return None
        return self._client

    async def close(self) -> None:
        if self._client:
            try:
                await self._client.close()
            except AttributeError:
                pass
            self._client = None

    async def _fetch_image_base64(self, url: str) -> str | None:
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    resp.raise_for_status()
                    content_type = resp.headers.get("content-type", "image/jpeg")
                    base64_data = base64.b64encode(await resp.read()).decode("utf-8")
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

        client = self._get_client()
        if not client:
            return VerificationResult(relevant=True, confidence=1.0, reason="AI unavailable")

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

        if hasattr(settings, "openai_model_name"):
            model = settings.openai_model_name
        else:
            model = settings.nvidia_vision_model if use_vision else settings.nvidia_model

        if use_vision and image_urls:
            content_parts: list[dict] = [{"type": "text", "text": user_prompt}]

            for url in image_urls[:3]:
                image_data = await self._fetch_image_base64(url)
                if image_data:
                    content_parts.append({"type": "image_url", "image_url": {"url": image_data}})

            if len(content_parts) == 1:
                use_vision = False
                if hasattr(settings, "openai_model_name"):
                    model = settings.openai_model_name
                else:
                    model = settings.nvidia_model

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content_parts},
            ]
        else:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

        try:
            if hasattr(client, "chat") and hasattr(client.chat, "completions"):
                resp = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=200,
                    response_format={"type": "json_object"},
                )
                content = resp.choices[0].message.content
            else:
                log.error(f"AI client does not support chat completions: {type(client)}")
                return None

            result = self._parse_response(content)
            return result

        except Exception as e:
            log.error(f"AI verification request failed: {e}", exc_info=True)
            return None

    def _parse_response(self, content: str) -> VerificationResult:
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        try:
            import json

            data = json.loads(content)
            return VerificationResult(
                relevant=bool(data.get("relevant", False)),
                confidence=float(data.get("confidence", 0.0)),
                reason=str(data.get("reason", "")),
            )
        except (json.JSONDecodeError, ValueError) as e:
            log.error(f"Failed to parse AI response: {e}")
            return VerificationResult(relevant=True, confidence=0.5, reason="Parse failed")


ai_verifier = AIVerifier()
