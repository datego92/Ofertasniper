import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from scraper import fetch_top_drops
from filter_engine import load_categories, filter_offers
from notifier import send_offers


def main() -> None:
    categories = load_categories()

    print("[main] Fetching 30-day top drops from CamelCamelCamel (amazon.es)...")
    offers = fetch_top_drops(domain="es")
    print(f"[main] Raw offers found: {len(offers)}")
    for o in offers[:5]:
        print(f"  TITLE: {o['title']}")
        print(f"  PRICE: {o['current_price']} | ORIGINAL: {o['original_price']} | DISCOUNT: {o['discount_pct']}%")

    offers_by_cat = filter_offers(offers, categories)
    total = sum(len(v) for v in offers_by_cat.values())
    print(f"[main] Offers matching categories: {total}")

    if offers_by_cat:
        send_offers(offers_by_cat, categories)
    else:
        print("[main] Nothing to notify.")

    print("[main] Done.")


if __name__ == "__main__":
    main()
