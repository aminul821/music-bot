"""Tiny JSON store for per-chat settings and approved users (survives restarts)."""
from __future__ import annotations

import json
import os
import threading

import config

DB_PATH = os.path.abspath(os.getenv("DB_PATH", "data/db.json"))
_lock = threading.Lock()


def _load() -> dict:
    try:
        with open(DB_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


_data: dict = _load()


def _save() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    tmp = DB_PATH + ".tmp"
    with _lock:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, DB_PATH)


def _chat(chat_id: int) -> dict:
    return _data.setdefault(str(chat_id), {})


# ---------------------------------------------------------------- settings

DEFAULTS = {
    # True: only admins/approved users can use playback controls
    "admin_mode": config.ADMIN_ONLY,
    # "everyone" or "admins": who can add songs with /play
    "play_mode": "everyone",
}


def get(chat_id: int, key: str):
    return _data.get(str(chat_id), {}).get(key, DEFAULTS[key])


def set(chat_id: int, key: str, value) -> None:  # noqa: A001
    _chat(chat_id)[key] = value
    _save()


# ---------------------------------------------------------------- extra allowed groups


def allowed_chats() -> set[int]:
    """Groups the owner/sudo added the bot to (on top of ALLOWED_CHATS)."""
    return {int(c) for c in _data.get("_allowed_chats", [])}


def allow_chat(chat_id: int) -> None:
    chats = _data.setdefault("_allowed_chats", [])
    if chat_id not in chats:
        chats.append(chat_id)
        _save()


def disallow_chat(chat_id: int) -> bool:
    chats = _data.get("_allowed_chats", [])
    if chat_id not in chats:
        return False
    chats.remove(chat_id)
    _save()
    return True


# ---------------------------------------------------------------- approved users


def approved(chat_id: int) -> dict[str, str]:
    """{user_id: display name} of users approved in this chat."""
    return _data.get(str(chat_id), {}).get("approved", {})


def is_approved(chat_id: int, user_id: int) -> bool:
    return str(user_id) in approved(chat_id)


def approve(chat_id: int, user_id: int, name: str) -> bool:
    users = _chat(chat_id).setdefault("approved", {})
    new = str(user_id) not in users
    users[str(user_id)] = name
    _save()
    return new


def unapprove(chat_id: int, user_id: int) -> bool:
    users = _chat(chat_id).get("approved", {})
    if users.pop(str(user_id), None) is None:
        return False
    _save()
    return True


def clear_approved(chat_id: int) -> int:
    users = _chat(chat_id).pop("approved", {})
    _save()
    return len(users)
