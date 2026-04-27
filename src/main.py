import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from scraper import fetch_top_drops, fetch_min_price
from filter_engine import load_categories, filter_offers
from notifier import send_offers


def main() -> None:
    categories = load_categories()

    min_discount = min(
        cat.get("min_discount_percent", 0) for cat in categories.values()
    )
    print(f"[main] Fetching 30-day top drops from CamelCamelCamel (amazon.es, min {min_discount}% off)...")
    offers = fetch_top_drops(domain="es", min_discount=min_discount)
    print(f"[main] Raw offers found: {len(offers)}")
    for o in offers[:5]:
        print(f"  TITLE: {o['title']}")
        print(f"  PRICE: {o['current_price']} | ORIGINAL: {o['original_price']} | DISCOUNT: {o['discount_pct']}%")

    offers_by_cat = filter_offers(offers, categories)
    total = sum(len(v) for v in offers_by_cat.values())
    print(f"[main] Offers matching categories: {total}")

    if not offers_by_cat:
        print("[main] Nothing to notify.")
        print("[main] Done.")
        return

    # Enriquecer con precio mínimo histórico (una llamada por oferta)
    print("[main] Fetching historical min prices...")
    for cat_offers in offers_by_cat.values():
        for offer in cat_offers:
            offer["min_price"] = fetch_min_price(offer["asin"], domain="es")

    send_offers(offers_by_cat, categories)
    print("[main] Done.")


if __name__ == "__main__":
    main()
