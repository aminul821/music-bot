from pyrogram.types import InlineKeyboardButton as Btn
from pyrogram.types import InlineKeyboardMarkup

import config


def player_markup(paused: bool = False, loop: bool = False) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                Btn("↺ 10s", callback_data="ctl:back"),
                Btn("▶️ Resume" if paused else "⏸ Pause", callback_data="ctl:resume" if paused else "ctl:pause"),
                Btn("10s ↻", callback_data="ctl:fwd"),
            ],
            [
                Btn("⏭ Skip", callback_data="ctl:skip"),
                Btn("⏹ Stop", callback_data="ctl:stop"),
                Btn("🔂 Loop: On" if loop else "🔁 Loop: Off", callback_data="ctl:loop"),
            ],
            [
                Btn("🔉 −", callback_data="ctl:voldown"),
                Btn("📜 Queue", callback_data="ctl:queue"),
                Btn("🔊 +", callback_data="ctl:volup"),
            ],
            [Btn("🗑 Close", callback_data="close")],
        ]
    )


def close_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[Btn("🗑 Close", callback_data="close")]])


def start_markup(bot_username: str) -> InlineKeyboardMarkup:
    rows = [
        [Btn("➕ Add me to your group", url=f"https://t.me/{bot_username}?startgroup=true&admin=manage_video_chats+invite_users+delete_messages")],
        [Btn("📖 Help & Commands", callback_data="help:main")],
    ]
    extra = []
    if config.SUPPORT_CHAT:
        extra.append(Btn("💬 Support", url=_link(config.SUPPORT_CHAT)))
    if config.UPDATES_CHANNEL:
        extra.append(Btn("📢 Updates", url=_link(config.UPDATES_CHANNEL)))
    if extra:
        rows.append(extra)
    return InlineKeyboardMarkup(rows)


def help_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [Btn("🎵 Play", callback_data="help:play"), Btn("🎛 Controls", callback_data="help:controls")],
            [Btn("📜 Queue", callback_data="help:queue"), Btn("⚙️ Other", callback_data="help:other")],
            [Btn("🗑 Close", callback_data="close")],
        ]
    )


def back_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[Btn("⬅️ Back", callback_data="help:main"), Btn("🗑 Close", callback_data="close")]])


def _link(value: str) -> str:
    return value if value.startswith("http") else f"https://t.me/{value.lstrip('@')}"
