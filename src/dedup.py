import json
from pathlib import Path

SENT_FILE = "data/sent_today.json"


def load_sent() -> set[str]:
    path = Path(SENT_FILE)
    if not path.exists():
        return set()
    with open(path, encoding="utf-8") as f:
        return set(json.load(f))


def save_sent(sent: set[str]) -> None:
    Path("data").mkdir(exist_ok=True)
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(list(sent), f)


def filter_new(offers_by_cat: dict, sent: set[str]) -> dict:
    result = {}
    for cat, offers in offers_by_cat.items():
        new = [o for o in offers if o["asin"] not in sent]
        if new:
            result[cat] = new
    return result


def mark_sent(offers_by_cat: dict, sent: set[str]) -> None:
    for offers in offers_by_cat.values():
        for offer in offers:
            sent.add(offer["asin"])
