"""
Integration tests for ai-goofish-monitor features.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime, timedelta

from core.parsers import (
    parse_search_results_json,
    parse_ratings_json,
    parse_user_head_json,
    calculate_reputation,
)
from core.filter import (
    matches_price_filter,
    matches_free_shipping,
    matches_publish_time,
    matches_region,
    apply_filters,
)
from core.parser import Listing
from db.models import Query


class TestParsers:
    def test_parse_search_results_json(self):
        test_data = {
            "data": {
                "resultList": [
                    {
                        "data": {
                            "item": {
                                "main": {
                                    "clickParam": {
                                        "args": {
                                            "publishTime": "1736715200000",
                                            "tag": "freeship",
                                            "wantNum": 5,
                                        }
                                    },
                                    "exContent": {
                                        "title": "iPhone 15 Pro Max",
                                        "price": [{"text": "当前价", "value": "9999"}],
                                        "picUrl": "https://example.com/image.jpg",
                                        "area": "上海浦东新区",
                                        "userNickName": "测试卖家",
                                        "itemId": "123456",
                                        "oriPrice": "原价12999",
                                        "userId": "seller789",
                                    },
                                }
                            },
                            "main": {"targetUrl": "fleamarket://item?id=123456"},
                        }
                    }
                ]
            }
        }

        import asyncio

        listings = asyncio.run(parse_search_results_json(test_data))
        assert len(listings) == 1
        listing = listings[0]
        assert listing.title == "iPhone 15 Pro Max"
        assert listing.id == "123456"
        assert listing.seller_name == "测试卖家"
        assert "包邮" in listing.tags

    def test_parse_ratings_json(self):
        test_data = {
            "data": {
                "cardList": [
                    {"cardData": {"rate": 1, "rateTagList": [{"text": "卖家"}]}},
                    {"cardData": {"rate": 1, "rateTagList": [{"text": "卖家"}]}},
                    {"cardData": {"rate": -1, "rateTagList": [{"text": "卖家"}]}},
                ]
            }
        }

        import asyncio

        ratings = asyncio.run(parse_ratings_json(test_data))
        assert ratings["seller_total"] == 3
        assert ratings["seller_positive"] == 2
        assert ratings["seller_rate"] == pytest.approx(66.67, abs=0.1)

    def test_calculate_reputation(self):
        ratings = {"seller_total": 100, "seller_rate": 95.0, "total_transactions": 150}
        user_head = {"registration_days": 730, "nick_name": "TestUser"}

        reputation = calculate_reputation(ratings, user_head)
        assert reputation["registration_days"] == 730
        assert "2年" in reputation["registration_text"]
        assert reputation["reputation_score"] > 0


class TestFilters:
    def test_matches_price_filter(self):
        listing = Listing(
            id="1",
            title="Test",
            price=100.0,
            image_url="",
            seller_id="s1",
            seller_name="Seller",
            location="Beijing",
            detail_url="http://example.com",
        )

        query = Query()
        query.min_price = 50
        query.max_price = 150
        assert matches_price_filter(listing, query) is True

        query.max_price = 80
        assert matches_price_filter(listing, query) is False

    def test_matches_free_shipping(self):
        listing_with_shipping = Listing(
            id="1",
            title="Test",
            price=100.0,
            image_url="",
            seller_id="s1",
            seller_name="Seller",
            location="Beijing",
            detail_url="http://example.com",
            tags=["包邮"],
        )

        listing_without_shipping = Listing(
            id="2",
            title="Test",
            price=100.0,
            image_url="",
            seller_id="s1",
            seller_name="Seller",
            location="Beijing",
            detail_url="http://example.com",
            tags=[],
        )

        query = Query()
        query.free_shipping = True
        assert matches_free_shipping(listing_with_shipping, query) is True
        assert matches_free_shipping(listing_without_shipping, query) is False

    def test_matches_region(self):
        listing = Listing(
            id="1",
            title="Test",
            price=100.0,
            image_url="",
            seller_id="s1",
            seller_name="Seller",
            location="上海浦东新区",
            detail_url="http://example.com",
        )

        query = Query()
        query.region = "上海"
        assert matches_region(listing, query) is True

        query.region = "北京"
        assert matches_region(listing, query) is False


class TestModels:
    def test_query_defaults(self):
        query = Query()
        assert query.keyword == ""
        assert query.ai_enabled is True
        assert query.ai_threshold == 0.7
        assert query.free_shipping is False
        assert isinstance(query.created_at, datetime)

    def test_listing_with_seller_info(self):
        listing = Listing(
            id="1",
            title="Test Item",
            price=999.0,
            image_url="http://img.com/1.jpg",
            seller_id="s123",
            seller_name="TestSeller",
            location="上海",
            detail_url="http://example.com/item/1",
            seller_rating=95.5,
            seller_registration_days=365,
            reputation_score=85.0,
        )

        assert listing.seller_rating == 95.5
        assert listing.seller_registration_days == 365
        assert listing.reputation_score == 85.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
