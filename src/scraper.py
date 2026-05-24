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

# CamelCamelCamel: categorías que mapea su feed RSS
# https://es.camelcamelcamel.com/top_drops/feed?category=X
_CAMEL_CATEGORIES = [
    "",               # todas (sin filtro)
    "video_games",
    "software",
    "electronics",
    "pc",
    "music",
    "books",
    "toys",
    "kitchen",
    "sports",
    "tools",
    "clothing",
    "beauty",
    "health",
    "automotive",
    "grocery",
    "movies",
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


def _fetch_image_from_amazon(asin: str, domain: str = "es") -> Optional[str]:
    """Intenta obtener la imagen del producto directamente desde Amazon.
    No requiere ScraperAPI — usa requests con cabeceras de navegador.
    Devuelve la URL de imagen o None si no se puede obtener."""
    # amazon.es, amazon.co.uk → dominios distintos
    tld_map = {"es": "es", "de": "de", "fr": "fr", "it": "it", "uk": "co.uk", "us": "com"}
    tld = tld_map.get(domain, "es")
    url = f"https://www.amazon.{tld}/dp/{asin}"
    try:
        resp = requests.get(url, headers=_AMAZON_HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"[scraper] Amazon image fetch: HTTP {resp.status_code} for {asin}")
            return None

        # og:image suele apuntar a la imagen principal del producto en alta resolución
        img_match = (
            re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', resp.text)
            or re.search(r'content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', resp.text)
        )
        if img_match:
            url_img = img_match.group(1)
            # Asegurarse de que es una imagen del CDN de Amazon, no un placeholder
            if "ssl-images-amazon.com" in url_img or "media-amazon.com" in url_img:
                return url_img

    except Exception as e:
        print(f"[scraper] Amazon image fetch error for {asin}: {e}")

    return None


def fetch_product_details(asin: str, domain: str = "es") -> dict:
    """Obtiene la imagen del producto directamente desde Amazon (gratis, sin APIs externas)."""
    result = {"title": None, "image_url": None}
    result["image_url"] = _fetch_image_from_amazon(asin, domain)
    if result["image_url"]:
        print(f"[scraper] {asin}: imagen obtenida de Amazon")
    else:
        print(f"[scraper] {asin}: no se pudo obtener imagen")
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
