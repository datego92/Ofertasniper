import json
import re
import requests
import feedparser
from typing import Optional

CAMEL_TOP_DROPS_URL = "https://{subdomain}camelcamelcamel.com/top_drops/feed"

_DOMAIN_SUBDOMAIN = {
    "es": "es.",
    "de": "de.",
    "fr": "fr.",
    "it": "it.",
    "uk": "uk.",
    "us": "",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# Cabeceras adicionales para parecer un navegador real al scrapear Amazon
_AMAZON_HEADERS = {
    **_HEADERS,
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

# Categorías soportadas por es.camelcamelcamel.com/top_drops/feed
# Las demás (books, toys, kitchen, sports…) devuelven feed malformado en ES
_CAMEL_CATEGORIES = [
    "",             # todas (sin filtro de categoría)
    "video_games",
    "software",
    "electronics",
    "pc",
    "music",
]


def fetch_top_drops(domain: str = "es", min_discount: int = 0) -> list[dict]:
    """Descarga el feed de CamelCamelCamel para TODAS las categorías y devuelve
    la lista de ofertas sin duplicados (un ASIN puede aparecer en varios feeds)."""
    subdomain = _DOMAIN_SUBDOMAIN.get(domain, "")
    base_url = CAMEL_TOP_DROPS_URL.format(subdomain=subdomain)

    seen_asins: set[str] = set()
    offers: list[dict] = []

    for cat in _CAMEL_CATEGORIES:
        params = f"days=30&percent={min_discount}"
        if cat:
            params = f"category={cat}&{params}"
        url = f"{base_url}?{params}"
        print(f"[scraper] Fetching: {url}")
        feed = feedparser.parse(url, request_headers=_HEADERS)

        if feed.bozo:
            print(f"[scraper] Feed parse warning ({cat or 'all'}): {feed.bozo_exception}")

        for entry in feed.entries:
            offer = _parse_entry(entry)
            if offer and offer["asin"] not in seen_asins:
                seen_asins.add(offer["asin"])
                offers.append(offer)

    print(f"[scraper] Total unique offers across all categories: {len(offers)}")
    return offers


def _extract_amazon_categories(html: str) -> list[str]:
    """Extrae la jerarquía de categorías de Amazon de la página de producto.

    Intenta en orden:
    1. JSON-LD BreadcrumbList (más fiable, datos estructurados).
    2. Breadcrumb HTML wayfinding (fallback).

    Devuelve una lista de strings, ej: ["Electrónica", "Audio y HiFi", "Auriculares"]
    """
    # ── Estrategia 1: JSON-LD ──────────────────────────────────────────────────
    for script in re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL):
        try:
            data = json.loads(script)
            # Puede ser un objeto o una lista de objetos
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "BreadcrumbList":
                    crumbs = sorted(item.get("itemListElement", []), key=lambda x: x.get("position", 0))
                    names = [c.get("name", "").strip() for c in crumbs if c.get("name")]
                    if names:
                        return names
        except (json.JSONDecodeError, AttributeError):
            continue

    # ── Estrategia 2: HTML wayfinding breadcrumb ───────────────────────────────
    wayfinding = re.search(
        r'id=["\']wayfinding-breadcrumbs_feature_div["\'][^>]*>(.*?)</div>',
        html, re.DOTALL
    )
    if wayfinding:
        names = re.findall(r'<a[^>]*>\s*([^<]+?)\s*</a>', wayfinding.group(1))
        if names:
            return [n.strip() for n in names if n.strip()]

    return []


def fetch_image(asin: str, domain: str = "es") -> Optional[str]:
    """Alias público — delega en fetch_product_details y devuelve solo la imagen."""
    return fetch_product_details(asin, domain)["image_url"]


def fetch_product_details(asin: str, domain: str = "es") -> dict:
    """Una sola petición a Amazon para obtener imagen Y categorías.

    Cuando Amazon responde (no siempre desde GitHub Actions / IPs AWS):
      - Extrae imagen via data-a-dynamic-image o og:image
      - Extrae categorías via JSON-LD BreadcrumbList o wayfinding HTML
    Cuando bloquea: devuelve imagen=None, cats=[] y los keywords del YAML
    actúan de fallback en la clasificación.
    """
    result: dict = {"title": None, "image_url": None, "amazon_cats": []}
    tld_map = {"es": "es", "de": "de", "fr": "fr", "it": "it", "uk": "co.uk", "us": "com"}
    tld = tld_map.get(domain, "es")
    url = f"https://www.amazon.{tld}/dp/{asin}"
    try:
        resp = requests.get(url, headers=_AMAZON_HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"[scraper] {asin}: Amazon HTTP {resp.status_code}")
            return result
        html = resp.text
        if "ap/captcha" in html or "robot check" in html.lower():
            print(f"[scraper] {asin}: Amazon CAPTCHA/robot block")
            return result

        # ── Imagen ────────────────────────────────────────────────────────────
        dynimg = re.search(r'data-a-dynamic-image=["\'](\{[^"\']+\})["\']', html)
        if dynimg:
            try:
                imgs = json.loads(dynimg.group(1))
                best = max(imgs.items(), key=lambda kv: kv[1][0] * kv[1][1])[0]
                if "amazon" in best:
                    result["image_url"] = best
            except (json.JSONDecodeError, ValueError, IndexError, KeyError):
                pass
        if not result["image_url"]:
            og = (
                re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
                or re.search(r'content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html)
            )
            if og:
                u = og.group(1)
                if "ssl-images-amazon.com" in u or "media-amazon.com" in u:
                    result["image_url"] = u

        # ── Categorías ────────────────────────────────────────────────────────
        result["amazon_cats"] = _extract_amazon_categories(html)
        print(f"[scraper] {asin}: img={'OK' if result['image_url'] else 'None'} cats={result['amazon_cats']}")

    except Exception as e:
        print(f"[scraper] {asin}: {e}")
    return result


def _parse_entry(entry) -> Optional[dict]:
    link = entry.get("link", "")
    asin_match = re.search(r"/product/([A-Z0-9]{10})", link)
    if not asin_match:
        return None

    asin = asin_match.group(1)
    raw_title = entry.get("title", "").strip()
    summary = entry.get("summary", "")

    # El summary contiene el título completo en el formato:
    # "Amazon price of TITULO COMPLETO dropped X%..."
    full_title_match = re.search(
        r"Amazon price of (.+?) (?:dropped|increased|has dropped|has increased)",
        summary,
        re.IGNORECASE,
    )
    if full_title_match:
        clean_title = full_title_match.group(1).strip()
    else:
        # Eliminar el sufijo de precio del título del RSS
        title_no_price = re.sub(r"\s*-\s*down\s+[\d.]+%.*$", "", raw_title, flags=re.IGNORECASE).strip()
        # Si está truncado ("Inicio...Final"), mostrar solo el inicio con ellipsis limpio
        if "..." in title_no_price:
            clean_title = title_no_price.split("...")[0].rstrip(" -,") + "…"
        else:
            clean_title = title_no_price

    current_price, original_price, discount_pct = _parse_prices(raw_title, summary)

    return {
        "asin": asin,
        "title": clean_title,
        "amazon_url": f"https://www.amazon.es/dp/{asin}",
        "image_url": None,
        "current_price": current_price,
        "original_price": original_price,
        "discount_pct": discount_pct,
    }


def _normalize_price(price_str: str) -> float:
    """
    Convierte un string de precio a float manejando formatos ES y US.

    Formatos soportados:
      ES con miles y decimal : "1.400,99" → 1400.99
      ES solo miles          : "1.400"    → 1400.0
      ES solo decimal        : "23,38"    → 23.38
      US con miles y decimal : "1,400.99" → 1400.99
      US solo decimal        : "108.99"   → 108.99
    """
    s = price_str.strip()
    # ES: separador de miles = punto, decimal = coma  →  "1.400,99" o "1.400"
    if re.match(r"^\d{1,3}(\.\d{3})+(,\d+)?$", s):
        s = s.replace(".", "").replace(",", ".")
    # ES: solo decimal con coma, sin miles  →  "23,38"
    elif re.match(r"^\d+,\d+$", s):
        s = s.replace(",", ".")
    # US: separador de miles = coma  →  "1,400.99" o "1,400"
    elif re.match(r"^\d{1,3}(,\d{3})+(\.\d+)?$", s):
        s = s.replace(",", "")
    # US/int: punto decimal normal  →  "108.99"  (ya es válido para float)
    return float(s)


# Patrón que captura precios en formato ES (1.400,99 | 1.400 | 23,38)
# y US ($1,400.99 | $108.99) incluyendo el separador de miles completo.
_PRICE_RE = re.compile(
    r"[€$]?\s*"
    r"("
    r"\d{1,3}(?:\.\d{3})+(?:,\d+)?"  # ES miles: 1.400 | 1.400,99
    r"|"
    r"\d{1,3}(?:,\d{3})+(?:\.\d+)?"  # US miles: 1,400 | 1,400.99
    r"|"
    r"\d+,\d+"                        # ES decimal sin miles: 23,38
    r"|"
    r"\d+\.\d+"                       # US/int decimal: 108.99
    r")"
    r"\s*[€$]?"
)


def _parse_prices(
    title: str, summary: str
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    text = f"{title} {summary}"

    # Formato ES: "down 11.85% (2,77€) to 20,61€ from 23,38€"
    # Formato US: "down 23.78% ($34.00) to $108.99 from $142.99"
    # Patrón de precio que soporta:
    #   ES miles+decimal : 1.400,99  ES solo miles: 1.400
    #   ES solo decimal  : 23,38     US decimal   : 108.99
    _PRICE_PAT = (
        r"\d{1,3}(?:\.\d{3})+(?:,\d+)?"   # ES miles  : 1.400 | 1.400,99
        r"|\d{1,3}(?:,\d{3})+(?:\.\d+)?"  # US miles  : 1,400 | 1,400.99
        r"|\d+[.,]\d+"                     # sin miles : 23,38 | 108.99
    )
    structured = re.search(
        rf"down\s+(\d+\.?\d*)\%.*?to\s+[€$]?\s*({_PRICE_PAT})\s*[€$]?.*?from\s+[€$]?\s*({_PRICE_PAT})\s*[€$]?",
        text,
        re.IGNORECASE,
    )
    if structured:
        discount_pct = float(structured.group(1))
        current_price = _normalize_price(structured.group(2))
        original_price = _normalize_price(structured.group(3))
        return current_price, original_price, discount_pct

    drop_match = re.search(r"(\d+\.?\d*)\s*%", text)
    discount_pct = float(drop_match.group(1)) if drop_match else None

    raw_prices = _PRICE_RE.findall(text)
    prices = sorted(
        {_normalize_price(p) for p in raw_prices if _normalize_price(p) > 0.5}
    )

    if len(prices) >= 2:
        current_price, original_price = prices[0], prices[-1]
    elif len(prices) == 1:
        current_price, original_price = prices[0], None
    else:
        current_price, original_price = None, None

    return current_price, original_price, discount_pct
