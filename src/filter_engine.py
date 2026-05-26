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


def _amazon_cat_matches(amazon_cats: list[str], amazon_nodes: list[str]) -> Optional[str]:
    """Comprueba si alguna categoría del breadcrumb de Amazon coincide con
    los nodos configurados. Devuelve el nodo coincidente o None."""
    amazon_cats_lower = [c.lower() for c in amazon_cats]
    for node in amazon_nodes:
        if node.lower() in amazon_cats_lower:
            return node
    return None


def classify_offer(offer: dict, categories: dict) -> Optional[str]:
    title = offer.get("title", "")
    asin = offer.get("asin", "")
    amazon_cats = offer.get("amazon_cats", [])  # breadcrumb de Amazon, ej. ["Videojuegos", "PS5"]

    for cat_key, cat in categories.items():
        # ── Filtro de exclusión (siempre se aplica) ───────────────────────────
        excluded_kw = next(
            (kw for kw in cat.get("exclude_keywords", []) if _keyword_matches(kw, title)), None
        )
        if excluded_kw:
            print(f"  [{asin}] excluded from '{cat_key}' by keyword '{excluded_kw}'")
            continue

        # ── Clasificación: Amazon primero, keywords como fallback ─────────────
        amazon_nodes = cat.get("amazon_nodes", [])
        keywords = cat.get("keywords", [])

        if amazon_cats and amazon_nodes:
            # Tenemos datos de Amazon → intentar match por categoría oficial
            matched_node = _amazon_cat_matches(amazon_cats, amazon_nodes)
            if matched_node:
                match_source = f"amazon_node '{matched_node}'"
            elif keywords:
                # No coincide por categoría Amazon → probar keywords
                matched_kw = next((kw for kw in keywords if _keyword_matches(kw, title)), None)
                if not matched_kw:
                    continue
                match_source = f"keyword '{matched_kw}'"
            elif not amazon_nodes:
                # Categoría sin amazon_nodes ni keywords → catch-all
                match_source = "*"
            else:
                continue
        elif keywords:
            # Sin datos de Amazon → clasificación solo por keywords
            matched_kw = next((kw for kw in keywords if _keyword_matches(kw, title)), None)
            if not matched_kw:
                continue
            match_source = f"keyword '{matched_kw}'"
        elif not keywords and not amazon_nodes:
            # Catch-all (sin keywords ni amazon_nodes)
            match_source = "*"
        else:
            continue

        # ── Filtros de descuento y precio ─────────────────────────────────────
        discount = offer.get("discount_pct") or 0
        min_disc = cat.get("min_discount_percent", 0)
        if discount < min_disc:
            print(f"  [{asin}] '{title[:40]}' → '{cat_key}' via {match_source} pero {discount}% < min {min_disc}%")
            continue

        max_price = cat.get("max_price") or 0
        current = offer.get("current_price")
        if max_price > 0 and current and current > max_price:
            print(f"  [{asin}] '{title[:40]}' → '{cat_key}' pero precio {current}€ > max {max_price}€")
            continue

        print(f"  [{asin}] MATCH '{cat_key}' via {match_source} — {discount}% off | cats Amazon: {amazon_cats}")
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
