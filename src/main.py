import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from scraper import fetch_top_drops, fetch_product_details
from filter_engine import load_categories, filter_offers
from notifier import send_offers
from dedup import load_sent, save_sent, filter_new, mark_sent
from title_cache import load_cache, save_cache


def main() -> None:
    categories = load_categories()
    sent = load_sent()
    title_cache = load_cache()

    print(f"[main] ASINs already sent today: {len(sent)}")
    print(f"[main] Titles in cache: {len(title_cache)}")

    min_discount = min(cat.get("min_discount_percent", 0) for cat in categories.values())
    print(f"[main] Fetching 30-day top drops (amazon.es, min {min_discount}% off)...")
    offers = fetch_top_drops(domain="es", min_discount=min_discount)
    print(f"[main] Raw offers found: {len(offers)}")

    # Enriquecer con imagen y categorías Amazon — caché primero, luego scraping
    cache_updated = False
    for offer in offers:
        asin = offer["asin"]
        if asin in title_cache:
            offer["title"] = title_cache[asin].get("title", offer["title"])
            offer["image_url"] = title_cache[asin].get("image_url") or offer.get("image_url")
            offer["amazon_cats"] = title_cache[asin].get("amazon_cats", [])
        else:
            # Pasar imagen del RSS para no hacer petición extra si ya la tenemos
            details = fetch_product_details(asin, domain="es", existing_image=offer.get("image_url"))
            offer["image_url"] = details["image_url"]
            offer["amazon_cats"] = details["amazon_cats"]
            title_cache[asin] = {
                "title": offer["title"],
                "image_url": details["image_url"],
                "amazon_cats": details["amazon_cats"],
            }
            cache_updated = True

    if cache_updated:
        save_cache(title_cache)
        print(f"[main] Title cache updated — now {len(title_cache)} entries")

    for o in offers:
        print(f"  [{o['asin']}] {o['title']}")

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
