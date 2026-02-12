import json
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Optional

log = logging.getLogger(__name__)


@dataclass
class RawListingAPI:
    id: str
    title: str
    price: float
    price_str: str
    image_url: str
    location: str
    seller_id: str
    seller_name: str
    detail_url: str
    original_price: Optional[str] = None
    wants_count: Optional[int] = None
    tags: list[str] = field(default_factory=list)
    raw_link: str = ""
    post_time: Optional[int] = None


async def parse_search_results_json(json_data: dict) -> list[RawListingAPI]:
    try:
        items = json_data.get("data", {}).get("resultList", [])
        if not items:
            log.debug(f"API响应中未找到商品列表 (resultList)")
            return []

        results = []
        for item in items:
            main_data = item.get("data", {}).get("item", {}).get("main", {}).get("exContent", {})
            click_params = (
                item.get("data", {})
                .get("item", {})
                .get("main", {})
                .get("clickParam", {})
                .get("args", {})
            )

            title = main_data.get("title", "未知标题")

            price_parts = main_data.get("price", [])
            if isinstance(price_parts, list):
                price_str = "".join(
                    [str(p.get("text", "")) for p in price_parts if isinstance(p, dict)]
                )
            else:
                price_str = str(price_parts)

            price_clean = price_str.replace("当前价", "").replace("¥", "").replace(",", "").strip()
            if not price_clean:
                price_clean = "0"
            if "万" in price_clean:
                price = float(price_clean.replace("万", "")) * 10000
            else:
                price = float(price_clean) if price_clean.replace(".", "").isdigit() else 0.0

            area = main_data.get("area", "地区未知")
            seller = main_data.get("userNickName", "匿名卖家")
            seller_id = main_data.get("userId", "")
            raw_link = item.get("data", {}).get("item", {}).get("main", {}).get("targetUrl", "")
            image_url = main_data.get("picUrl", "")
            pub_time_ts = click_params.get("publishTime", "")
            item_id = main_data.get("itemId", "未知ID")
            original_price = main_data.get("oriPrice", "暂无")
            wants_count = click_params.get("wantNum")

            tags = []
            if click_params.get("tag") == "freeship":
                tags.append("包邮")

            r1_tags = main_data.get("fishTags", {}).get("r1", {}).get("tagList", [])
            if isinstance(r1_tags, list):
                for tag_item in r1_tags:
                    content = tag_item.get("data", {}).get("content", "")
                    if "验货宝" in content:
                        tags.append("验货宝")

            post_time = None
            if pub_time_ts and str(pub_time_ts).isdigit():
                try:
                    post_time = int(pub_time_ts) // 1000
                except (ValueError, TypeError):
                    pass

            results.append(
                RawListingAPI(
                    id=str(item_id),
                    title=title,
                    price=price,
                    price_str=f"¥{price_str}",
                    image_url=image_url,
                    location=area,
                    seller_id=str(seller_id),
                    seller_name=seller,
                    post_time=post_time,
                    detail_url=raw_link.replace("fleamarket://", "https://www.goofish.com/"),
                    original_price=original_price,
                    wants_count=wants_count,
                    tags=tags,
                    raw_link=raw_link,
                )
            )

        log.info(f"成功解析到 {len(results)} 条商品信息")
        return results

    except Exception as e:
        log.error(f"JSON数据处理异常: {e}", exc_info=True)
        return []


async def parse_detail_json(json_data: dict) -> dict:
    try:
        data = json_data.get("data", {})
        main_data = data.get("item", {}).get("main", {})
        ex_content = main_data.get("exContent", {})

        images = []
        if "images" in ex_content:
            images = ex_content.get("images", [])
        elif "picUrl" in ex_content:
            images = [{"url": ex_content.get("picUrl", "")}]

        description = ex_content.get("description", "")
        seller_id = main_data.get("userId", "")
        seller_name = main_data.get("userNickName", "")

        return {
            "images": images,
            "description": description,
            "seller_id": seller_id,
            "seller_name": seller_name,
        }

    except Exception as e:
        log.error(f"详情JSON解析异常: {e}", exc_info=True)
        return {
            "images": [],
            "description": "",
            "seller_id": "",
            "seller_name": "",
        }


async def parse_ratings_json(json_data: dict) -> dict:
    try:
        cards = json_data.get("data", {}).get("cardList", [])

        seller_positive = 0
        seller_total = 0
        buyer_positive = 0
        buyer_total = 0

        for card in cards:
            card_data = card.get("cardData", {})
            role_tag = card_data.get("rateTagList", [])

            if role_tag:
                role = role_tag[0].get("text", "") if isinstance(role_tag, list) else ""
                rate = card_data.get("rate", 0)

                if "卖家" in role:
                    seller_total += 1
                    if rate == 1:
                        seller_positive += 1
                elif "买家" in role:
                    buyer_total += 1
                    if rate == 1:
                        buyer_positive += 1

        seller_rate = (seller_positive / seller_total * 100) if seller_total > 0 else 0
        buyer_rate = (buyer_positive / buyer_total * 100) if buyer_total > 0 else 0

        return {
            "seller_positive": seller_positive,
            "seller_total": seller_total,
            "seller_rate": seller_rate,
            "buyer_positive": buyer_positive,
            "buyer_total": buyer_total,
            "buyer_rate": buyer_rate,
            "total_transactions": seller_total + buyer_total,
        }

    except Exception as e:
        log.error(f"评价JSON解析异常: {e}", exc_info=True)
        return {
            "seller_positive": 0,
            "seller_total": 0,
            "seller_rate": 0,
            "buyer_positive": 0,
            "buyer_total": 0,
            "buyer_rate": 0,
            "total_transactions": 0,
        }


async def parse_user_head_json(json_data: dict) -> dict:
    try:
        main_data = json_data.get("data", {}).get("item", {}).get("main", {})
        user_head = main_data.get("userHead", {})

        registration_days = user_head.get("regDays", 0)
        nick_name = user_head.get("nickName", "")
        user_id = user_head.get("userId", "")

        return {
            "registration_days": int(registration_days) if str(registration_days).isdigit() else 0,
            "nick_name": nick_name,
            "user_id": user_id,
        }

    except Exception as e:
        log.error(f"用户头部信息JSON解析异常: {e}", exc_info=True)
        return {
            "registration_days": 0,
            "nick_name": "",
            "user_id": "",
        }


def calculate_reputation(ratings: dict, user_head: dict) -> dict:
    registration_days = user_head.get("registration_days", 0)
    seller_total = ratings.get("seller_total", 0)
    seller_rate = ratings.get("seller_rate", 0)
    total_transactions = ratings.get("total_transactions", 0)

    registration_text = f"{registration_days}天"
    if registration_days >= 365:
        years = registration_days // 365
        days = registration_days % 365
        if days > 0:
            registration_text = f"{years}年{days}天"
        else:
            registration_text = f"{years}年"

    reputation_score = 0.0
    if seller_total > 0:
        rating_weight = 0.4
        transaction_weight = 0.3
        registration_weight = 0.3

        normalized_rate = seller_rate / 100
        normalized_transactions = min(total_transactions / 1000, 1.0)
        normalized_registration = min(registration_days / 3650, 1.0)

        reputation_score = (
            normalized_rate * rating_weight
            + normalized_transactions * transaction_weight
            + normalized_registration * registration_weight
        ) * 100

    return {
        "registration_days": registration_days,
        "registration_text": registration_text,
        "seller_total": seller_total,
        "seller_rate": seller_rate,
        "total_transactions": total_transactions,
        "reputation_score": round(reputation_score, 2),
    }
