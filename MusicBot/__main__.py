import glob
import os
import shutil

from pyrogram import idle
from pyrogram.types import BotCommand

import config
from MusicBot import LOGGER
from MusicBot.core import player  # noqa: F401  (registers voice chat handlers)
from MusicBot.core.clients import assistant, bot, call

COMMANDS = [
    BotCommand("play", "🎵 Play audio (name / link / reply)"),
    BotCommand("vplay", "📺 Play video (name / link / reply)"),
    BotCommand("stream", "🔗 Play a direct audio link / radio"),
    BotCommand("vstream", "📡 Play a direct video link / live"),
    BotCommand("pause", "⏸ Pause"),
    BotCommand("resume", "▶️ Resume"),
    BotCommand("skip", "⏭ Next track"),
    BotCommand("stop", "⏹ Stop & leave"),
    BotCommand("queue", "📜 Show queue"),
    BotCommand("np", "🎧 Now playing"),
    BotCommand("seek", "⏩ Seek to position"),
    BotCommand("volume", "🔊 Volume 1-200"),
    BotCommand("loop", "🔁 Loop current track"),
    BotCommand("shuffle", "🔀 Shuffle queue"),
    BotCommand("approve", "✅ Approve a user (admins)"),
    BotCommand("unapprove", "🚫 Unapprove a user (admins)"),
    BotCommand("approved", "📋 Approved users (admins)"),
    BotCommand("settings", "⚙️ Chat settings (admins)"),
    BotCommand("ping", "🏓 Bot status"),
    BotCommand("help", "📖 Help"),
]


def _clean_downloads() -> None:
    for path in glob.glob(os.path.join(config.DOWNLOAD_DIR, "*")):
        try:
            os.remove(path)
        except OSError:
            pass


async def main() -> None:
    _clean_downloads()
    if not any(shutil.which(rt) for rt in ("deno", "node", "bun")):
        LOGGER.warning(
            "No JavaScript runtime found: YouTube downloads may fail with HTTP 403. "
            "Install Deno: curl -fsSL https://deno.land/install.sh | sh"
        )
    if config.COOKIES_FILE and os.path.isfile(config.COOKIES_FILE):
        LOGGER.info("Using YouTube cookies from %s", config.COOKIES_FILE)
    else:
        LOGGER.warning(
            "No YouTube cookies set: cloud servers usually get \"Sign in to confirm you're not a bot\". "
            "Send cookies.txt to the bot and reply /setcookies, or set COOKIES_FILE."
        )
    if not shutil.which("ffmpeg"):
        LOGGER.error("ffmpeg is not installed: sudo apt install ffmpeg")
    await bot.start()
    await call.start()  # also starts the assistant client
    # In-memory sessions start with an empty peer cache: load the assistant's chats.
    try:
        async for _ in assistant.get_dialogs():
            pass
    except Exception as e:
        LOGGER.warning("Couldn't load assistant dialogs: %s", e)
    try:
        await bot.set_bot_commands(COMMANDS)
    except Exception as e:
        LOGGER.warning("Couldn't set bot commands: %s", e)
    if config.ALLOWED_CHATS:
        LOGGER.info("Locked to group(s): %s", ", ".join(map(str, config.ALLOWED_CHATS)))
    else:
        LOGGER.warning("ALLOWED_CHATS is empty: the bot works in any group. Send /id in your group and set it.")
    LOGGER.info("Bot @%s started with assistant @%s", bot.me.username, assistant.me.username or assistant.me.id)
    if config.OWNER_ID:
        try:
            await bot.send_message(config.OWNER_ID, f"✅ <b>{config.BOT_NAME}</b> is online! 🎶")
        except Exception:
            pass
    await idle()
    await bot.stop()
    await assistant.stop()


if __name__ == "__main__":
    bot.run(main())
