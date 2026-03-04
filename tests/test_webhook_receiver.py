from core.webhook_receiver import (
    _build_superbuy_url,
    _convert_goofish_short_url,
    _extract_listing_notification,
    _extract_title_content,
    _parse_cny_amount,
    _should_drop_notification,
)


def test_extract_title_content_from_dict() -> None:
    title, content = _extract_title_content({"title": "t", "content": "c"})
    assert title == "t"
    assert content == "c"


def test_extract_title_content_fallback_keys() -> None:
    title, content = _extract_title_content({"notification_title": "t", "message": "c"})
    assert title == "t"
    assert content == "c"


def test_extract_title_content_from_string() -> None:
    title, content = _extract_title_content("hello")
    assert title
    assert content == "hello"


def test_should_drop_auth_expired_notification() -> None:
    assert _should_drop_notification(
        "Goofish Monitor",
        "Goofish authentication has expired. Update cookies.json and restart the bot.",
    )


def test_should_not_drop_normal_notification() -> None:
    assert not _should_drop_notification(
        "New listing matched",
        "Found item: iPhone 15 Pro 256GB",
    )


def test_parse_cny_amount() -> None:
    assert _parse_cny_amount("¥1,299") == 1299
    assert _parse_cny_amount("1.2万") == 12000
    assert _parse_cny_amount(None) is None


def test_convert_goofish_short_url() -> None:
    source = "https://www.goofish.com/item?id=9282837465&foo=bar"
    short = _convert_goofish_short_url(source)
    assert short.startswith("https://pages.goofish.com/sharexy")
    assert "bfp=%7B%22id%22%3A9282837465%7D" in short


def test_build_superbuy_url_contains_encoded_source() -> None:
    source = "https://www.goofish.com/item?id=9282837465&foo=bar"
    result = _build_superbuy_url(source)
    assert "superbuy.com" in result
    assert "https%3A%2F%2Fwww.goofish.com%2Fitem%3Fid%3D9282837465" in result


def test_extract_listing_notification_from_structured_payload() -> None:
    payload = {
        "title": "Alert",
        "content": "Fallback",
        "meta": {
            "listing_title": "PS5 Slim",
            "reason": "Price under fair-market range and trusted seller.",
            "listing_description": "Like new, comes with two controllers.",
            "price_cny_text": "¥2,100",
            "listing_link_pc": "https://www.goofish.com/item?id=1234567890",
            "listing_images": ["https://img.example/1.jpg", "https://img.example/2.jpg"],
        },
    }

    parsed = _extract_listing_notification(payload, payload["content"])
    assert parsed is not None
    assert parsed.listing_title == "PS5 Slim"
    assert parsed.reason.startswith("Price under")
    assert parsed.description.startswith("Like new")
    assert parsed.price_cny == 2100
    assert parsed.goofish_url.endswith("id=1234567890")
    assert parsed.goofish_short_url.startswith("https://pages.goofish.com/sharexy")
    assert "superbuy.com" in parsed.superbuy_url
    assert parsed.image_url == "https://img.example/1.jpg"


def test_extract_listing_notification_from_plain_content() -> None:
    content = (
        "Price: ¥888\n"
        "Reason: Verified photos + low price\n"
        "Description: Used for 2 months, no repairs\n"
        "PC link: https://www.goofish.com/item?id=9876543210"
    )

    parsed = _extract_listing_notification(content, content)
    assert parsed is not None
    assert parsed.price_cny == 888
    assert parsed.reason == "Verified photos + low price"
    assert parsed.description == "Used for 2 months, no repairs"
    assert parsed.goofish_url.endswith("id=9876543210")
    assert parsed.goofish_short_url.startswith("https://pages.goofish.com/sharexy")
