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


def fetch_product_details(asin: str, domain: str = "es") -> dict:
    """Obtiene título completo e imagen desde CamelCamelCamel (evita bloqueos de Amazon)."""
    subdomain = _DOMAIN_SUBDOMAIN.get(domain, "")
    url = f"https://{subdomain}camelcamelcamel.com/product/{asin}"
    result = {"title": None, "image_url": None}
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=8)
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

    # Debug temporal para ver el contenido real del feed
    if "..." in raw_title:
        print(f"[DEBUG] TITLE: {raw_title}")
        print(f"[DEBUG] SUMMARY: {summary[:300]}")
        print(f"[DEBUG] KEYS: {list(entry.keys())}")

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
        # Fallback: eliminar el sufijo de precio del título del RSS
        clean_title = re.sub(r"\s*-\s*down\s+[\d.]+%.*$", "", raw_title, flags=re.IGNORECASE).strip()

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


def _parse_prices(
    title: str, summary: str
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    text = f"{title} {summary}"

    # Formato ES: "down 11.85% (2,77€) to 20,61€ from 23,38€"
    # Formato US: "down 23.78% ($34.00) to $108.99 from $142.99"
    structured = re.search(
        r"down\s+(\d+\.?\d*)\%.*?to\s+[€$]?(\d+[.,]\d{2})[€$]?.*?from\s+[€$]?(\d+[.,]\d{2})[€$]?",
        text,
        re.IGNORECASE,
    )
    if structured:
        discount_pct = float(structured.group(1))
        current_price = float(structured.group(2).replace(",", "."))
        original_price = float(structured.group(3).replace(",", "."))
        return current_price, original_price, discount_pct

    drop_match = re.search(r"(\d+\.?\d*)\s*%", text)
    discount_pct = float(drop_match.group(1)) if drop_match else None

    raw_prices = re.findall(r"[€$]?(\d+[.,]\d{2})[€$]?", text)
    prices = sorted({float(p.replace(",", ".")) for p in raw_prices if float(p.replace(",", ".")) > 0.5})

    if len(prices) >= 2:
        current_price, original_price = prices[0], prices[-1]
    elif len(prices) == 1:
        current_price, original_price = prices[0], None
    else:
        current_price, original_price = None, None

    return current_price, original_price, discount_pct
