import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parsers import (
    parse_search_results_json,
    parse_detail_json,
    parse_ratings_json,
    parse_user_head_json,
    calculate_reputation,
)


async def test_parsers():
    print("Testing parsers...")

    test_search_json = {
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
                                    "title": "测试商品 iPhone 15 Pro Max",
                                    "price": [{"text": "当前价", "value": "9999"}],
                                    "picUrl": "https://example.com/image.jpg",
                                    "area": "上海浦东新区",
                                    "userNickName": "测试卖家",
                                    "itemId": "test123",
                                    "oriPrice": "原价12999",
                                    "userId": "seller456",
                                },
                            }
                        },
                        "main": {"targetUrl": "fleamarket://item?id=test123"},
                    }
                }
            ]
        }
    }

    listings = await parse_search_results_json(test_search_json)
    print(f"Parsed {len(listings)} listings")
    if listings:
        print(f"First listing: {listings[0]}")

    test_ratings_json = {
        "data": {"cardList": [{"cardData": {"rate": 1, "rateTagList": [{"text": "卖家"}]}}]}
    }

    ratings = await parse_ratings_json(test_ratings_json)
    print(f"Parsed ratings: {ratings}")

    test_head_json = {
        "data": {"item": {"main": {"userHead": {"regDays": "365", "nickName": "测试卖家"}}}}
    }

    head = await parse_user_head_json(test_head_json)
    print(f"Parsed user head: {head}")

    reputation = calculate_reputation(ratings, head)
    print(f"Calculated reputation: {reputation}")

    print("\nAll parser tests passed!")


if __name__ == "__main__":
    asyncio.run(test_parsers())
