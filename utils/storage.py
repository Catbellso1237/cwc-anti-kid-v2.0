"""
Lưu trữ cảnh báo (warn) bằng file JSON đơn giản.
Phù hợp cho bot chạy trên Termux / Codespaces / Windows mà không cần setup database.
"""

import json
import os
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
WARN_FILE = os.path.join(DATA_DIR, "warnings.json")


def _ensure_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(WARN_FILE):
        with open(WARN_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def _load() -> dict[str, Any]:
    _ensure_file()
    with open(WARN_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(data: dict[str, Any]):
    _ensure_file()
    with open(WARN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_warning(guild_id: int, user_id: int, moderator_id: int, reason: str) -> int:
    """Thêm 1 cảnh báo, trả về tổng số cảnh báo hiện tại của user đó."""
    data = _load()
    gkey = str(guild_id)
    ukey = str(user_id)
    data.setdefault(gkey, {})
    data[gkey].setdefault(ukey, [])
    data[gkey][ukey].append({"moderator_id": moderator_id, "reason": reason})
    _save(data)
    return len(data[gkey][ukey])


def get_warnings(guild_id: int, user_id: int) -> list:
    data = _load()
    return data.get(str(guild_id), {}).get(str(user_id), [])


def clear_warnings(guild_id: int, user_id: int) -> int:
    """Xoá toàn bộ cảnh báo, trả về số lượng đã xoá."""
    data = _load()
    gkey = str(guild_id)
    ukey = str(user_id)
    count = len(data.get(gkey, {}).get(ukey, []))
    if gkey in data and ukey in data[gkey]:
        del data[gkey][ukey]
        _save(data)
    return count

                  
