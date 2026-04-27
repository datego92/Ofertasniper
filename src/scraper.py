import re
import feedparser
from typing import Optional

CAMEL_TOP_DROPS_URL = "https://camelcamelcamel.com/top_drops/feed"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def fetch_top_drops(domain: str = "es") -> list[dict]:
    url = f"{CAMEL_TOP_DROPS_URL}?category=video_games&domain={domain}"
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

    # Porcentaje de bajada: "30% drop", "30% off", "30% descuento"
    drop_match = re.search(
        r"(\d+(?:\.\d+)?)\s*%\s*(?:drop|off|descuento|bajada)",
        text,
        re.IGNORECASE,
    )
    discount_pct = float(drop_match.group(1)) if drop_match else None

    # Precios en formato europeo: €29,99 / 29.99€ / EUR 29.99
    raw_prices = re.findall(
        r"(?:€|EUR\s{0,2})(\d{1,3}[.,]\d{2})", text, re.IGNORECASE
    )
    if not raw_prices:
        raw_prices = re.findall(r"(\d{1,3}[.,]\d{2})\s*€", text)

    prices = sorted({float(p.replace(",", ".")) for p in raw_prices})

    if len(prices) >= 2:
        current_price, original_price = prices[0], prices[-1]
        if not discount_pct and original_price > 0:
            discount_pct = round((1 - current_price / original_price) * 100, 1)
    elif len(prices) == 1:
        current_price, original_price = prices[0], None
    else:
        current_price, original_price = None, None

    return current_price, original_price, discount_pct
