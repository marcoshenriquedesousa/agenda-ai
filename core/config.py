import json
from core.paths import BASE_DIR

_CONFIG_PATH = BASE_DIR / "config.json"
_cache: dict | None = None


def get_config() -> dict:
    global _cache
    if _cache is None:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            _cache = json.load(f)
    return _cache


def invalidate():
    global _cache
    _cache = None
