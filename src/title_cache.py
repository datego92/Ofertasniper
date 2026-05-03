import json
from pathlib import Path

CACHE_FILE = "data/title_cache.json"


def load_cache() -> dict:
    path = Path(CACHE_FILE)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_cache(cache: dict) -> None:
    Path("data").mkdir(exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
