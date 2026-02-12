from dataclasses import dataclass, field

from core.scanner import RawListing


@dataclass
class Listing:
    id: str
    title: str
    price: float
    image_url: str
    seller_id: str
    seller_name: str
    location: str
    detail_url: str
    seller_rating: float = 0.0
    seller_registration_days: int = 0
    seller_registration_text: str = ""
    reputation_score: float = 0.0
    price_str: str = ""
    tags: list = field(default_factory=list)
    post_time: str | None = None
    original_price: str | None = None
    wants_count: int | None = None
    post_time: str | None = None
    original_price: str | None = None
    wants_count: int | None = None


def normalize_listing(raw: RawListing) -> Listing:
    return Listing(
        id=raw.id,
        title=raw.title.strip(),
        price=raw.price,
        price_str=getattr(raw, "price_str", f"¥{raw.price}"),
        image_url=raw.image_url,
        seller_id=raw.seller_id,
        seller_name=raw.seller_name,
        location=raw.location,
        detail_url=raw.detail_url,
        original_price=getattr(raw, "original_price", None),
        wants_count=getattr(raw, "wants_count", None),
        tags=getattr(raw, "tags", []),
        post_time=getattr(raw, "post_time", None),
    )


def normalize_listings(raw_listings: list[RawListing]) -> list[Listing]:
    return [normalize_listing(r) for r in raw_listings]
