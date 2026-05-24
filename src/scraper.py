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


def fetch_top_drops(domain: str = "es", min_discount: int = 0) -> list[dict]:
    subdomain = _DOMAIN_SUBDOMAIN.get(domain, "")
    url = CAMEL_TOP_DROPS_URL.format(subdomain=subdomain) + f"?category=video_games&days=30&percent={min_discount}"
    print(f"[scraper] Fetching: {url}")
    feed = feedparser.parse(url, request_headers=_HEADERS)

    if feed.bozo:
        print(f"[scraper] Feed parse warning: {feed.bozo_exception}")

    offers = []
    for entry in feed.entries:
        offer = _parse_entry(entry)
        if offer:
            offers.append(offer)

    return offers


def fetch_product_details(asin: str, domain: str = "es", scraperapi_key: str = "") -> dict:
    """Obtiene título completo e imagen via ScraperAPI (bypasea Cloudflare)."""
    result = {"title": None, "image_url": None}
    if not scraperapi_key:
        return result

    subdomain = _DOMAIN_SUBDOMAIN.get(domain, "")
    target = f"https://{subdomain}camelcamelcamel.com/product/{asin}"
    try:
        resp = requests.get(
            "http://api.scraperapi.com",
            params={"api_key": scraperapi_key, "url": target},
            timeout=30,
        )
        print(f"[scraper] {asin}: HTTP {resp.status_code}")
        if resp.status_code != 200:
            return result

        title_match = (
            re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', resp.text)
            or re.search(r'content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']', resp.text)
        )
        if title_match:
            result["title"] = title_match.group(1).strip()

        img_match = (
            re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', resp.text)
            or re.search(r'content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', resp.text)
        )
        if img_match:
            result["image_url"] = img_match.group(1)

    except Exception as e:
        print(f"[scraper] Details fetch failed for {asin}: {e}")

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
