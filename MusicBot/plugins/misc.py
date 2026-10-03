import os
import time

from pyrogram import Client, filters
from pyrogram.types import Message

import config
from MusicBot.core import queue
from MusicBot.core.clients import call
from MusicBot.utils.decorators import get_admins, group_only
from MusicBot.utils.filters import command

BOOT_TIME = time.time()


def _uptime() -> str:
    secs = int(time.time() - BOOT_TIME)
    d, secs = divmod(secs, 86400)
    h, secs = divmod(secs, 3600)
    m, s = divmod(secs, 60)
    return (f"{d}d " if d else "") + f"{h}h {m}m {s}s"


@Client.on_message(command("ping"))
async def ping_cmd(client: Client, message: Message):
    start = time.perf_counter()
    msg = await message.reply_text("🏓 <b>Pinging…</b>")
    api_ms = (time.perf_counter() - start) * 1000
    try:
        call_ms = f"{call.ping:.2f} ms"
    except Exception:
        call_ms = "n/a"
    await msg.edit_text(
        "<b>🏓 Pong!</b>\n\n"
        f"⚡ <b>Bot API:</b> <code>{api_ms:.0f} ms</code>\n"
        f"🎙 <b>Voice engine:</b> <code>{call_ms}</code>\n"
        f"🎧 <b>Active chats:</b> <code>{len(queue.active_chats())}</code>\n"
        f"⏱ <b>Uptime:</b> <code>{_uptime()}</code>"
    )


@Client.on_message(command("reload", "admincache"))
@group_only
async def reload_cmd(client: Client, message: Message):
    await get_admins(message.chat.id, refresh=True)
    await message.reply_text("✅ <b>Admin list refreshed.</b>")


@Client.on_message(command("stats") & filters.user(list(config.SUDO_USERS) or [0]))
async def stats_cmd(client: Client, message: Message):
    chats = queue.active_chats()
    lines = [f"<b>📊 Stats</b>\n\n🎧 Active voice chats: <b>{len(chats)}</b>", f"⏱ Uptime: <code>{_uptime()}</code>"]
    for cid in chats[:20]:
        cur = queue.get(cid).current
        lines.append(f"• <code>{cid}</code> — {cur.title[:40] if cur else '—'}")
    await message.reply_text("\n".join(lines))


@Client.on_message(command("setcookies") & filters.user(list(config.SUDO_USERS) or [0]))
async def setcookies_cmd(client: Client, message: Message):
    doc = message.reply_to_message.document if message.reply_to_message else None
    if not doc:
        return await message.reply_text(
            "<b>Usage:</b> send your YouTube <code>cookies.txt</code> (Netscape format) and reply to it "
            "with <code>/setcookies</code>.\n\n"
            "Export it from a browser logged into YouTube with the "
            "<i>Get cookies.txt LOCALLY</i> extension. Use a spare account."
        )
    if doc.file_size and doc.file_size > 5 * 1024 * 1024:
        return await message.reply_text("❌ That file is too large to be a cookies.txt.")
    tmp = await message.reply_to_message.download(file_name=os.path.abspath("cookies.txt.new"))
    with open(tmp, encoding="utf-8", errors="ignore") as f:
        content = f.read()
    if "youtube.com" not in content or "\t" not in content:
        os.remove(tmp)
        return await message.reply_text("❌ That doesn't look like a Netscape-format YouTube cookies.txt.")
    target = os.path.abspath(config.COOKIES_FILE or "cookies.txt")
    os.replace(tmp, target)
    os.chmod(target, 0o600)
    config.COOKIES_FILE = target
    try:
        await message.reply_to_message.delete()  # cookies are account credentials
    except Exception:
        pass
    await message.reply_text("✅ <b>YouTube cookies saved.</b> Try <code>/play</code> again.")
