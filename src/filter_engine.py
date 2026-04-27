import yaml
from typing import Optional


def load_categories(config_path: str = "config/categories.yaml") -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)["categories"]


def classify_offer(offer: dict, categories: dict) -> Optional[str]:
    title_lower = offer.get("title", "").lower()

    for cat_key, cat in categories.items():
        excluded = any(kw.lower() in title_lower for kw in cat.get("exclude_keywords", []))
        if excluded:
            continue

        matched = any(kw.lower() in title_lower for kw in cat.get("keywords", []))
        if not matched:
            continue

        discount = offer.get("discount_pct") or 0
        if discount < cat.get("min_discount_percent", 0):
            continue

        max_price = cat.get("max_price")
        current = offer.get("current_price")
        if max_price and current and current > max_price:
            continue

        return cat_key

    return None


def filter_offers(offers: list[dict], categories: dict) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {key: [] for key in categories}

    for offer in offers:
        cat = classify_offer(offer, categories)
        if cat:
            offer["category"] = cat
            result[cat].append(offer)

    return {k: v for k, v in result.items() if v}
