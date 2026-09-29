"""
Lưu danh sách UID bị ban TOÀN CỤC (global ban) — áp dụng cho mọi server mà bot có mặt,
không phải chỉ 1 server riêng lẻ như lệnh /ban thông thường.
"""

import json
import os
import time
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
GLOBAL_BAN_FILE = os.path.join(DATA_DIR, "global_bans.json")


def _ensure_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(GLOBAL_BAN_FILE):
        with open(GLOBAL_BAN_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def _load() -> dict[str, Any]:
    _ensure_file()
    with open(GLOBAL_BAN_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(data: dict[str, Any]):
    _ensure_file()
    with open(GLOBAL_BAN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_global_ban(user_id: int, reason: str, banned_by: int):
    data = _load()
    data[str(user_id)] = {"reason": reason, "banned_by": banned_by, "timestamp": time.time()}
    _save(data)


def remove_global_ban(user_id: int) -> bool:
    data = _load()
    key = str(user_id)
    if key in data:
        del data[key]
        _save(data)
        return True
    return False


def is_globally_banned(user_id: int) -> bool:
    return str(user_id) in _load()


def get_global_ban_info(user_id: int) -> dict | None:
    return _load().get(str(user_id))


def list_global_bans() -> dict:
    return _load()
          
