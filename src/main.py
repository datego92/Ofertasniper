import os
import sys

# Allow running as `python src/main.py` from the project root
sys.path.insert(0, os.path.dirname(__file__))

from scraper import fetch_top_drops
from filter_engine import load_categories, filter_offers
from history import load_history, save_history, is_duplicate, mark_notified, cleanup_history
from notifier import send_offers


def main() -> None:
    categories = load_categories()
    history = load_history()
    cleanup_history(history)

    print("[main] Fetching top drops from CamelCamelCamel (amazon.es)...")
    offers = fetch_top_drops(domain="es")
    print(f"[main] Raw offers found: {len(offers)}")

    offers_by_cat = filter_offers(offers, categories)
    total_matched = sum(len(v) for v in offers_by_cat.values())
    print(f"[main] Offers matching categories: {total_matched}")

    new_offers_by_cat: dict = {}
    for cat, cat_offers in offers_by_cat.items():
        new = [o for o in cat_offers if not is_duplicate(o["asin"], o.get("current_price"), history)]
        if new:
            new_offers_by_cat[cat] = new

    total_new = sum(len(v) for v in new_offers_by_cat.values())
    print(f"[main] New (non-duplicate) offers to notify: {total_new}")

    if new_offers_by_cat:
        send_offers(new_offers_by_cat, categories)
        for cat_offers in new_offers_by_cat.values():
            for offer in cat_offers:
                mark_notified(offer, history)
    else:
        print("[main] Nothing new to notify.")

    save_history(history)
    print("[main] Done.")


if __name__ == "__main__":
    main()
