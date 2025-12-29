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
    title_lower = listing.title.lower()
    return not any(term.lower() in title_lower for term in query.exclude_terms)


def apply_filters(listing: Listing, query: Query) -> bool:
    return (
        matches_price_filter(listing, query)
        and matches_include_terms(listing, query)
        and matches_exclude_terms(listing, query)
    )


def filter_listings(listings: list[Listing], query: Query) -> list[Listing]:
    return [item for item in listings if apply_filters(item, query)]
