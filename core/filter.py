from core.parser import Listing
from db.models import Query


def matches_price_filter(listing: Listing, query: Query) -> bool:
    if query.min_price is not None and listing.price < query.min_price:
        return False
    if query.max_price is not None and listing.price > query.max_price:
        return False
    return True


def matches_include_terms(listing: Listing, query: Query) -> bool:
    if not query.include_terms:
        return True
    title_lower = listing.title.lower()
    return all(term.lower() in title_lower for term in query.include_terms)


def matches_exclude_terms(listing: Listing, query: Query) -> bool:
    if not query.exclude_terms:
        return True
    title_lower = listing.lower()
    return not any(term.lower() in title_lower for term in query.exclude_terms)


def matches_free_shipping(listing: Listing, query: Query) -> bool:
    if not query.free_shipping:
        return True
    if not listing.tags:
        return False
    return "包邮" in listing.tags


def matches_publish_time(listing: Listing, query: Query) -> bool:
    if query.new_publish_hours is None or query.new_publish_hours <= 0:
        return True
    if not listing.post_time:
        return True

    from datetime import datetime, timedelta

    post_datetime = datetime.strptime(listing.post_time, "%Y-%m-%d %H:%M")
    cutoff = datetime.utcnow() - timedelta(hours=query.new_publish_hours)
    return post_datetime >= cutoff


def matches_region(listing: Listing, query: Query) -> bool:
    if not query.region or not listing.location:
        return True
    region_lower = query.region.lower()
    location_lower = listing.location.lower()
    return region_lower in location_lower


def apply_filters(listing: Listing, query: Query) -> bool:
    return (
        matches_price_filter(listing, query)
        and matches_include_terms(listing, query)
        and matches_exclude_terms(listing, query)
        and matches_free_shipping(listing, query)
        and matches_publish_time(listing, query)
        and matches_region(listing, query)
    )


def filter_listings(listings: list[Listing], query: Query) -> list[Listing]:
    return [item for item in listings if apply_filters(item, query)]
