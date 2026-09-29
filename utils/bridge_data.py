"""
Lưu danh sách kênh "cầu nối chat" (chat bridge) — mỗi server chỉ định 1 kênh,
bot sẽ relay tin nhắn qua lại giữa các kênh này ở TẤT CẢ server đã setup,
dùng webhook để hiện đúng tên + avatar người gửi gốc.
"""

import json
import os
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
BRIDGE_FILE = os.path.join(DATA_DIR, "bridge_channels.json")


def _ensure_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(BRIDGE_FILE):
        with open(BRIDGE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def _load() -> dict[str, Any]:
    _ensure_file()
    with open(BRIDGE_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(data: dict[str, Any]):
    _ensure_file()
    with open(BRIDGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_bridge(guild_id: int, channel_id: int, webhook_url: str):
    data = _load()
    data[str(guild_id)] = {"channel_id": channel_id, "webhook_url": webhook_url}
    _save(data)


def remove_bridge(guild_id: int) -> bool:
    data = _load()
    key = str(guild_id)
    if key in data:
        del data[key]
        _save(data)
        return True
    return False


def get_bridge(guild_id: int) -> dict | None:
    return _load().get(str(guild_id))


def get_filter_config() -> dict:
    data = _load()
    filter_cfg = data.get("_filter", {})
    filter_cfg.setdefault("banned_words", [])
    filter_cfg.setdefault("block_invites", True)
    return filter_cfg


def set_filter_config(**kwargs):
    data = _load()
    filter_cfg = data.get("_filter", {"banned_words": [], "block_invites": True})
    filter_cfg.update(kwargs)
    data["_filter"] = filter_cfg
    _save(data)


def list_bridges() -> dict:
    """Trả về danh sách bridge theo guild, KHÔNG bao gồm key cấu hình filter nội bộ."""
    data = _load()
    return {k: v for k, v in data.items() if k != "_filter"}
               
