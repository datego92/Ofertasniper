import re
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


def fetch_top_drops(domain: str = "es") -> list[dict]:
    subdomain = _DOMAIN_SUBDOMAIN.get(domain, "")
    url = CAMEL_TOP_DROPS_URL.format(subdomain=subdomain) + "?category=video_games"
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


def _parse_entry(entry) -> Optional[dict]:
    link = entry.get("link", "")
    asin_match = re.search(r"/product/([A-Z0-9]{10})", link)
    if not asin_match:
        return None

    asin = asin_match.group(1)
    title = entry.get("title", "").strip()
    summary = entry.get("summary", "")

    current_price, original_price, discount_pct = _parse_prices(title, summary)

    return {
        "asin": asin,
        "title": title,
        "amazon_url": f"https://www.amazon.es/dp/{asin}",
        "camel_url": link,
        "current_price": current_price,
        "original_price": original_price,
        "discount_pct": discount_pct,
    }


def _parse_prices(
    title: str, summary: str
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    text = f"{title} {summary}"

    # Formato real del feed: "down 23.78% ($34.00) to $108.99 from $142.99"
    # o versión europea:     "down 23.78% (€34,00) to €108,99 from €142,99"
    structured = re.search(
        r"down\s+(\d+\.?\d*)\%.*?to\s+[€$](\d+[.,]\d{2}).*?from\s+[€$](\d+[.,]\d{2})",
        text,
        re.IGNORECASE,
    )
    if structured:
        discount_pct = float(structured.group(1))
        current_price = float(structured.group(2).replace(",", "."))
        original_price = float(structured.group(3).replace(",", "."))
        return current_price, original_price, discount_pct

    # Fallback: buscar cualquier porcentaje + precios sueltos
    drop_match = re.search(r"(\d+\.?\d*)\s*%", text)
    discount_pct = float(drop_match.group(1)) if drop_match else None

    raw_prices = re.findall(r"[€$](\d+[.,]\d{2})", text)
    prices = sorted({float(p.replace(",", ".")) for p in raw_prices})

    if len(prices) >= 2:
        current_price, original_price = prices[0], prices[-1]
    elif len(prices) == 1:
        current_price, original_price = prices[0], None
    else:
        current_price, original_price = None, None

    return current_price, original_price, discount_pct
