import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

HISTORY_FILE = "data/history.json"
DEDUP_HOURS = 24
RETENTION_DAYS = 90


def load_history() -> dict:
    path = Path(HISTORY_FILE)
    if not path.exists():
        return {"notified": {}}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_history(history: dict) -> None:
    Path("data").mkdir(exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def is_duplicate(asin: str, current_price: Optional[float], history: dict) -> bool:
    entry = history.get("notified", {}).get(asin)
    if not entry:
        return False

    last_ts = datetime.fromisoformat(entry["timestamp"])
    if datetime.now(timezone.utc) - last_ts > timedelta(hours=DEDUP_HOURS):
        return False

    # Si el precio bajó más de un 5% respecto a la última notificación, volver a notificar
    prev_price = entry.get("price")
    if current_price and prev_price and current_price < prev_price * 0.95:
        return False

    return True


def mark_notified(offer: dict, history: dict) -> None:
    history.setdefault("notified", {})[offer["asin"]] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "price": offer.get("current_price"),
        "title": offer.get("title", ""),
    }


def cleanup_history(history: dict) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    notified = history.get("notified", {})
    stale = [
        asin
        for asin, entry in notified.items()
        if datetime.fromisoformat(entry["timestamp"]) < cutoff
    ]
    for asin in stale:
        del notified[asin]
    if stale:
        print(f"[history] Cleaned {len(stale)} entries older than {RETENTION_DAYS} days")
