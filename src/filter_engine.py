import yaml
from typing import Optional


def load_categories(config_path: str = "config/categories.yaml") -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)["categories"]


def _keyword_matches(keyword: str, title: str) -> bool:
    kw = keyword.lower()
    t = title.lower()

    # Coincidencia directa
    if kw in t:
        return True

    # Títulos truncados: "Inicio del título...final del título"
    # CamelCamelCamel parte el título en el medio, lo que puede cortar keywords
    # como "PlayStation 4" → "...tation 4 [...]"
    # Comprobamos si el keyword fue partido exactamente en el punto de truncación
    if "..." in t:
        before, after = t.split("...", 1)
        min_len = 4  # Mínimo de chars para evitar falsos positivos

        # ¿El sufijo del keyword aparece al inicio de 'after'?
        # Ejemplo: kw="playstation 4", after="tation 4 [importación...]"
        # kw[5:] = "tation 4" → after.startswith("tation 4") → True
        for i in range(min_len, len(kw)):
            if after.startswith(kw[i:]):
                return True

        # ¿El prefijo del keyword aparece al final de 'before'?
        for i in range(min_len, len(kw)):
            if before.endswith(kw[:i]):
                return True

    return False


def classify_offer(offer: dict, categories: dict) -> Optional[str]:
    title = offer.get("title", "")

    for cat_key, cat in categories.items():
        excluded = any(
            _keyword_matches(kw, title)
            for kw in cat.get("exclude_keywords", [])
        )
        if excluded:
            continue

        matched = any(
            _keyword_matches(kw, title)
            for kw in cat.get("keywords", [])
        )
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
