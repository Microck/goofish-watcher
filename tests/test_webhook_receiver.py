from core.webhook_receiver import _extract_title_content


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
