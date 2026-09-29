"""
Lưu cấu hình riêng cho từng server (guild) bằng JSON, không cần database ngoài.
Dùng cho: bật/tắt auto-defense 24/7, kênh mod-log, whitelist bot tin cậy.
"""

import json
import os
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CONFIG_FILE = os.path.join(DATA_DIR, "guild_config.json")

DEFAULT_CONFIG = {
    "autodefense": False,       # Chế độ tự động phòng vệ 24/7
    "mod_log_channel": None,    # ID kênh nhận cảnh báo raid / bot giả
    "mod_announcement_channel": None,  # ID kênh thông báo riêng cho đội mod
    "mod_role_id": None,        # ID role mod (tự tìm hoặc tự tạo qua lệnh setup)
    "bot_announcement_channel": None,  # ID kênh nhận thông báo TỪ CHỦ BOT (globalannounce)
    "join_threshold": 6,        # Số lượng member join tối đa trong khoảng thời gian dưới
    "join_window_seconds": 10,  # Khoảng thời gian tính raid (giây)
    "trusted_bot_ids": [],      # Danh sách ID các bot được coi là an toàn, bỏ qua kiểm tra fake bot

    "antilink_enabled": False,          # Bật/tắt anti-link
    "antilink_mode": "invite_only",     # "invite_only" = chỉ chặn invite Discord | "all_links" = chặn mọi link trừ whitelist
    "antilink_whitelist_domains": [],   # Domain được phép khi antilink_mode = "all_links"
    "antilink_whitelist_channels": [],  # Kênh không áp dụng anti-link
}


def _ensure_file():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def _load() -> dict[str, Any]:
    _ensure_file()
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(data: dict[str, Any]):
    _ensure_file()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_guild_config(guild_id: int) -> dict:
    data = _load()
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(data.get(str(guild_id), {}))
    return cfg


def set_guild_config(guild_id: int, **kwargs) -> dict:
    data = _load()
    gkey = str(guild_id)
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(data.get(gkey, {}))
    cfg.update(kwargs)
    data[gkey] = cfg
    _save(data)
    return cfg


def is_autodefense_on(guild_id: int) -> bool:
    return get_guild_config(guild_id).get("autodefense", False)
          
