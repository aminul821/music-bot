from pyrogram.types import InlineKeyboardButton as Btn
from pyrogram.types import InlineKeyboardMarkup

import config


def player_markup(paused: bool = False, loop: bool = False, progress: str | None = None) -> InlineKeyboardMarkup:
    rows = []
    if progress:
        rows.append([Btn(progress, callback_data="ctl:np")])
    rows += [
        [
            Btn("⏮ 10s", callback_data="ctl:back"),
            Btn("▶️" if paused else "⏸", callback_data="ctl:resume" if paused else "ctl:pause"),
            Btn("⏭", callback_data="ctl:skip"),
            Btn("⏹", callback_data="ctl:stop"),
            Btn("10s ⏩", callback_data="ctl:fwd"),
        ],
        [
            Btn("🔉", callback_data="ctl:voldown"),
            Btn("🔂 ᴏɴ" if loop else "🔁 ʟᴏᴏᴘ", callback_data="ctl:loop"),
            Btn("🔀", callback_data="ctl:shuffle"),
            Btn("📜", callback_data="ctl:queue"),
            Btn("🔊", callback_data="ctl:volup"),
        ],
        [Btn("✖ ᴄʟᴏsᴇ", callback_data="close")],
    ]
    return InlineKeyboardMarkup(rows)


def close_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[Btn("✖ ᴄʟᴏsᴇ", callback_data="close")]])


def start_markup(bot_username: str) -> InlineKeyboardMarkup:
    rows = [
        [Btn("➕ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ ➕", url=f"https://t.me/{bot_username}?startgroup=true&admin=manage_video_chats+invite_users+delete_messages")],
        [Btn("📖 ʜᴇʟᴘ & ᴄᴏᴍᴍᴀɴᴅs", callback_data="help:main")],
    ]
    extra = []
    if config.SUPPORT_CHAT:
        extra.append(Btn("💬 sᴜᴘᴘᴏʀᴛ", url=_link(config.SUPPORT_CHAT)))
    if config.UPDATES_CHANNEL:
        extra.append(Btn("📢 ᴜᴘᴅᴀᴛᴇs", url=_link(config.UPDATES_CHANNEL)))
    if extra:
        rows.append(extra)
    return InlineKeyboardMarkup(rows)


def help_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [Btn("🎵 ᴘʟᴀʏ", callback_data="help:play"), Btn("📺 ᴠɪᴅᴇᴏ", callback_data="help:video")],
            [Btn("🎛 ᴄᴏɴᴛʀᴏʟs", callback_data="help:controls"), Btn("📜 ǫᴜᴇᴜᴇ", callback_data="help:queue")],
            [Btn("🛡 ᴀᴅᴍɪɴ", callback_data="help:admin"), Btn("⚙️ ᴏᴛʜᴇʀ", callback_data="help:other")],
            [Btn("✖ ᴄʟᴏsᴇ", callback_data="close")],
        ]
    )


def back_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[Btn("⬅️ ʙᴀᴄᴋ", callback_data="help:main"), Btn("✖ ᴄʟᴏsᴇ", callback_data="close")]])


def _link(value: str) -> str:
    return value if value.startswith("http") else f"https://t.me/{value.lstrip('@')}"
