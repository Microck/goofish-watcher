from dataclasses import dataclass

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


def normalize_listing(raw: RawListing) -> Listing:
    return Listing(
        id=raw.id,
        title=raw.title.strip(),
        price=raw.price,
        image_url=raw.image_url,
        seller_id=raw.seller_id,
        seller_name=raw.seller_name,
        location=raw.location,
        detail_url=raw.detail_url,
    )


def normalize_listings(raw_listings: list[RawListing]) -> list[Listing]:
    return [normalize_listing(r) for r in raw_listings]
