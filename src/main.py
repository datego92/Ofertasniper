import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from scraper import fetch_top_drops, fetch_product_details
from filter_engine import load_categories, filter_offers
from notifier import send_offers
from dedup import load_sent, save_sent, filter_new, mark_sent


def main() -> None:
    categories = load_categories()
    sent = load_sent()
    print(f"[main] ASINs already sent today: {len(sent)}")

    min_discount = min(cat.get("min_discount_percent", 0) for cat in categories.values())
    print(f"[main] Fetching 30-day top drops (amazon.es, min {min_discount}% off)...")
    offers = fetch_top_drops(domain="es", min_discount=min_discount)
    print(f"[main] Raw offers found: {len(offers)}")

    # Enriquecer todos los títulos e imágenes desde Amazon antes de filtrar
    # (el RSS trunca los títulos, lo que rompe el matching de keywords)
    print("[main] Fetching full titles and images from Amazon...")
    for offer in offers:
        details = fetch_product_details(offer["asin"])
        if details["title"]:
            offer["title"] = details["title"]
        offer["image_url"] = details["image_url"]
        print(f"  [{offer['asin']}] {offer['title'][:70]}")

    offers_by_cat = filter_offers(offers, categories)
    total = sum(len(v) for v in offers_by_cat.values())
    print(f"[main] Offers matching categories: {total}")

    new_offers_by_cat = filter_new(offers_by_cat, sent)
    total_new = sum(len(v) for v in new_offers_by_cat.values())
    print(f"[main] New offers (not sent today): {total_new}")

    if not new_offers_by_cat:
        print("[main] Nothing new to notify.")
        print("[main] Done.")
        return

    send_offers(new_offers_by_cat, categories)
    mark_sent(new_offers_by_cat, sent)
    save_sent(sent)
    print("[main] Done.")


if __name__ == "__main__":
    main()
