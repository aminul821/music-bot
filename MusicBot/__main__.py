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
    BotCommand("play", "Play audio from YouTube / a file"),
    BotCommand("vplay", "Play video from YouTube / a file"),
    BotCommand("pause", "Pause playback"),
    BotCommand("resume", "Resume playback"),
    BotCommand("skip", "Skip to the next track"),
    BotCommand("stop", "Stop and leave the voice chat"),
    BotCommand("queue", "Show the queue"),
    BotCommand("np", "Now playing"),
    BotCommand("seek", "Seek to a position"),
    BotCommand("volume", "Set volume (1-200)"),
    BotCommand("loop", "Loop the current track"),
    BotCommand("shuffle", "Shuffle the queue"),
    BotCommand("ping", "Bot status"),
    BotCommand("help", "Show help"),
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
    if not shutil.which("ffmpeg"):
        LOGGER.error("ffmpeg is not installed: sudo apt install ffmpeg")
    await bot.start()
    await call.start()  # also starts the assistant client
    try:
        await bot.set_bot_commands(COMMANDS)
    except Exception as e:
        LOGGER.warning("Couldn't set bot commands: %s", e)
    LOGGER.info("Bot @%s started with assistant @%s", bot.me.username, assistant.me.username or assistant.me.id)
    if config.OWNER_ID:
        try:
            await bot.send_message(config.OWNER_ID, "✅ <b>Music bot is online.</b>")
        except Exception:
            pass
    await idle()
    await bot.stop()
    await assistant.stop()


if __name__ == "__main__":
    bot.run(main())
