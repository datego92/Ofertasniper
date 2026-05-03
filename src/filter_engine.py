import yaml
from typing import Optional


def load_categories(config_path: str = "config/categories.yaml") -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)["categories"]


_MIN_FUZZY_SEGMENT = 7  # Segmento mínimo para evitar falsos positivos

def _keyword_matches(keyword: str, title: str) -> bool:
    kw = keyword.lower()
    t = title.lower()

    # Coincidencia directa
    if kw in t:
        return True

    # Fuzzy solo para keywords largos (>= 7 chars) en títulos truncados
    # Ejemplo: "PlayStation 4" partido como "Vengean...tation 4"
    # kw[5:] = "tation 4" (8 chars >= 7) → coincide con inicio de 'after'
    if len(kw) >= _MIN_FUZZY_SEGMENT and "..." in t:
        before, after = t.split("...", 1)

        for i in range(1, len(kw)):
            suffix = kw[i:]
            if len(suffix) >= _MIN_FUZZY_SEGMENT and after.startswith(suffix):
                return True

        for i in range(1, len(kw)):
            prefix = kw[:i]
            if len(prefix) >= _MIN_FUZZY_SEGMENT and before.endswith(prefix):
                return True

    return False


def classify_offer(offer: dict, categories: dict) -> Optional[str]:
    title = offer.get("title", "")
    asin = offer.get("asin", "")

    for cat_key, cat in categories.items():
        excluded_kw = next(
            (kw for kw in cat.get("exclude_keywords", []) if _keyword_matches(kw, title)), None
        )
        if excluded_kw:
            print(f"  [{asin}] excluded from '{cat_key}' by keyword '{excluded_kw}'")
            continue

        matched_kw = next(
            (kw for kw in cat.get("keywords", []) if _keyword_matches(kw, title)), None
        )
        if not matched_kw:
            continue

        discount = offer.get("discount_pct") or 0
        min_disc = cat.get("min_discount_percent", 0)
        if discount < min_disc:
            print(f"  [{asin}] '{title[:40]}' matched '{cat_key}' via '{matched_kw}' but discount {discount}% < {min_disc}%")
            continue

        max_price = cat.get("max_price")
        current = offer.get("current_price")
        if max_price and current and current > max_price:
            print(f"  [{asin}] '{title[:40]}' matched '{cat_key}' but price {current}€ > max {max_price}€")
            continue

        print(f"  [{asin}] MATCH '{cat_key}' via keyword '{matched_kw}' — {discount}% off")
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
