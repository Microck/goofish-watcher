from core.webhook_receiver import _extract_title_content, _should_drop_notification


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
