import html
import re

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from MusicBot.core import player, queue
from MusicBot.utils.buttons import close_markup, player_markup
from MusicBot.utils.decorators import admin_only, callback_is_admin, group_only
from MusicBot.utils.filters import command
from MusicBot.utils.formatters import esc, fmt_time, mention, parse_time, progress_bar


def _by(message: Message) -> str:
    return mention(message.from_user) if message.from_user else "Admin"


def queue_text(chat_id: int, limit: int = 15) -> str:
    state = queue.get(chat_id)
    if not state.tracks:
        return "📭 <b>The queue is empty.</b>"
    cur = state.current
    lines = [
        "<b>📜 Queue</b>\n",
        f"<b>▶️ Now:</b> {esc(cur.title, 50)}",
        f"   <code>{fmt_time(cur.elapsed())} / {fmt_time(cur.duration)}</code> • {cur.requested_by}",
    ]
    upcoming = state.tracks[1:]
    if upcoming:
        lines.append("\n<b>⏭ Up next:</b>")
        for i, t in enumerate(upcoming[:limit], start=1):
            lines.append(f"<b>{i}.</b> {esc(t.title, 45)} <code>[{fmt_time(t.duration)}]</code>")
        if len(upcoming) > limit:
            lines.append(f"<i>…and {len(upcoming) - limit} more</i>")
        total = sum(t.duration for t in upcoming)
        lines.append(f"\n🎶 <b>{len(upcoming)}</b> upcoming • ⏱ <code>{fmt_time(total)}</code>")
    if state.loop:
        lines.append(f"🔂 Loop: <b>{state.loop}</b> more time(s)")
    return "\n".join(lines)


def np_text(chat_id: int) -> str | None:
    state = queue.get(chat_id)
    t = state.current
    if not t:
        return None
    elapsed = t.elapsed()
    status = "⏸ Paused" if state.paused else "▶️ Playing"
    return (
        f"<b>{status}</b>  •  {'📺 Video' if t.video else '🎧 Audio'}\n\n"
        f"🎵 <b>{esc(t.title)}</b>\n\n"
        f"<code>{fmt_time(elapsed)}</code> {progress_bar(elapsed, t.duration)} <code>{fmt_time(t.duration)}</code>\n\n"
        f"🔊 Volume: <b>{state.volume}%</b>  •  🔁 Loop: <b>{state.loop or 'Off'}</b>\n"
        f"👤 Requested by: {t.requested_by}"
    )


async def _require_playing(message: Message) -> bool:
    if not queue.get(message.chat.id).current:
        await message.reply_text("❌ Nothing is playing right now.")
        return False
    return True


@Client.on_message(command("pause"))
@admin_only
async def pause_cmd(client: Client, message: Message):
    if not await _require_playing(message):
        return
    if await player.pause(message.chat.id):
        await message.reply_text(f"⏸ <b>Paused</b> by {_by(message)}")
    else:
        await message.reply_text("ℹ️ Already paused.")


@Client.on_message(command("resume"))
@admin_only
async def resume_cmd(client: Client, message: Message):
    if not await _require_playing(message):
        return
    if await player.resume(message.chat.id):
        await message.reply_text(f"▶️ <b>Resumed</b> by {_by(message)}")
    else:
        await message.reply_text("ℹ️ Already playing.")


@Client.on_message(command("skip", "next"))
@admin_only
async def skip_cmd(client: Client, message: Message):
    if not await _require_playing(message):
        return
    nxt = await player.skip(message.chat.id)
    if nxt is None:
        await message.reply_text(f"⏭ <b>Skipped</b> by {_by(message)} — queue is now empty.")
    else:
        await message.reply_text(f"⏭ <b>Skipped</b> by {_by(message)}")


@Client.on_message(command("stop", "end"))
@admin_only
async def stop_cmd(client: Client, message: Message):
    await player.stop(message.chat.id)
    await message.reply_text(f"⏹ <b>Stopped</b> by {_by(message)}. Queue cleared and left the voice chat.")


@Client.on_message(command("loop", "repeat"))
@admin_only
async def loop_cmd(client: Client, message: Message):
    if not await _require_playing(message):
        return
    state = queue.get(message.chat.id)
    arg = message.command[1].lower() if len(message.command) > 1 else ""
    if arg in ("off", "0", "disable"):
        state.loop = 0
    elif arg.isdigit():
        state.loop = max(1, min(int(arg), 10))
    else:
        state.loop = 0 if state.loop else 10
    await message.reply_text(
        f"🔂 Loop set to <b>{state.loop}</b> time(s)." if state.loop else "🔁 Loop <b>disabled</b>."
    )


@Client.on_message(command("shuffle"))
@admin_only
async def shuffle_cmd(client: Client, message: Message):
    state = queue.get(message.chat.id)
    if len(state.tracks) < 3:
        return await message.reply_text("ℹ️ Need at least 2 upcoming tracks to shuffle.")
    state.shuffle()
    await message.reply_text("🔀 <b>Queue shuffled!</b>\n\n" + queue_text(message.chat.id, 10), reply_markup=close_markup())


@Client.on_message(command("remove"))
@admin_only
async def remove_cmd(client: Client, message: Message):
    state = queue.get(message.chat.id)
    if len(message.command) < 2 or not message.command[1].isdigit():
        return await message.reply_text("<b>Usage:</b> <code>/remove 2</code> (position from /queue)")
    pos = int(message.command[1])
    if pos < 1 or pos >= len(state.tracks):
        return await message.reply_text("❌ Invalid position.")
    removed = state.tracks.pop(pos)
    if removed.download and not removed.download.done():
        removed.download.cancel()
    await message.reply_text(f"🗑 Removed <b>{esc(removed.title)}</b> from the queue.")


@Client.on_message(command("clear", "clearqueue"))
@admin_only
async def clear_cmd(client: Client, message: Message):
    state = queue.get(message.chat.id)
    removed = state.tracks[1:]
    del state.tracks[1:]
    for t in removed:
        if t.download and not t.download.done():
            t.download.cancel()
    await message.reply_text(f"🧹 Cleared <b>{len(removed)}</b> upcoming track(s).")


@Client.on_message(command("seek"))
@admin_only
async def seek_cmd(client: Client, message: Message):
    if not await _require_playing(message):
        return
    if len(message.command) < 2:
        return await message.reply_text("<b>Usage:</b> <code>/seek 1:30</code> or <code>/seek +30</code> / <code>/seek -10</code>")
    arg = message.command[1]
    cur = queue.get(message.chat.id).current
    if arg[0] in "+-":
        delta = parse_time(arg[1:])
        if delta is None:
            return await message.reply_text("❌ Invalid time.")
        target = cur.elapsed() + (delta if arg[0] == "+" else -delta)
    else:
        target = parse_time(arg)
        if target is None:
            return await message.reply_text("❌ Invalid time. Use <code>90</code> or <code>1:30</code>.")
    try:
        await player.seek(message.chat.id, target)
    except player.PlayerError as e:
        return await message.reply_text(str(e))
    await message.reply_text(f"⏩ Seeked to <code>{fmt_time(max(target, 0) or 1)}</code>")


@Client.on_message(command("volume", "vol"))
@admin_only
async def volume_cmd(client: Client, message: Message):
    if not await _require_playing(message):
        return
    if len(message.command) < 2 or not message.command[1].isdigit():
        return await message.reply_text(
            f"🔊 Current volume: <b>{queue.get(message.chat.id).volume}%</b>\n<b>Usage:</b> <code>/volume 1-200</code>"
        )
    try:
        vol = await player.set_volume(message.chat.id, int(message.command[1]))
    except Exception as e:
        return await message.reply_text(
            f"❌ Couldn't change volume (assistant may need admin rights).\n<code>{esc(str(e), 150)}</code>"
        )
    await message.reply_text(f"🔊 Volume set to <b>{vol}%</b>")


@Client.on_message(command("queue", "q"))
@group_only
async def queue_cmd(client: Client, message: Message):
    await message.reply_text(queue_text(message.chat.id), reply_markup=close_markup(), disable_web_page_preview=True)


@Client.on_message(command("np", "now", "nowplaying", "current"))
@group_only
async def np_cmd(client: Client, message: Message):
    text = np_text(message.chat.id)
    if not text:
        return await message.reply_text("❌ Nothing is playing right now.")
    state = queue.get(message.chat.id)
    await message.reply_text(text, reply_markup=player_markup(state.paused, state.loop > 0))


# ---------------------------------------------------------------- inline control panel


@Client.on_callback_query(filters.regex(r"^ctl:"))
async def control_cb(client: Client, query: CallbackQuery):
    chat_id = query.message.chat.id
    action = query.data.split(":", 1)[1]
    state = queue.get(chat_id)

    if action == "queue":
        text = queue_text(chat_id, 10)
        return await query.answer(_plain(text)[:200], show_alert=True)

    if not state.current:
        return await query.answer("Nothing is playing.", show_alert=True)
    if not await callback_is_admin(query):
        return

    user = query.from_user.first_name
    try:
        if action == "pause":
            await player.pause(chat_id)
            await query.answer("⏸ Paused")
        elif action == "resume":
            await player.resume(chat_id)
            await query.answer("▶️ Resumed")
        elif action == "skip":
            await query.answer("⏭ Skipping…")
            nxt = await player.skip(chat_id)
            if nxt is None:
                await client.send_message(chat_id, f"⏭ Skipped by {esc(user)} — queue is now empty.")
            return
        elif action == "stop":
            await query.answer("⏹ Stopped")
            await player.stop(chat_id)
            await client.send_message(chat_id, f"⏹ <b>Stopped</b> by {esc(user)}.")
            return
        elif action == "loop":
            state.loop = 0 if state.loop else 10
            await query.answer("🔂 Loop on" if state.loop else "🔁 Loop off")
        elif action in ("volup", "voldown"):
            vol = await player.set_volume(chat_id, state.volume + (20 if action == "volup" else -20))
            return await query.answer(f"🔊 Volume: {vol}%")
        elif action in ("fwd", "back"):
            cur = state.current
            if cur.duration == 0:
                return await query.answer("Can't seek in a live stream.", show_alert=True)
            await query.answer("⏩ +10s" if action == "fwd" else "⏪ −10s")
            await player.seek(chat_id, cur.elapsed() + (10 if action == "fwd" else -10))
            return
    except Exception as e:
        return await query.answer(f"Error: {e}"[:200], show_alert=True)

    try:
        await query.message.edit_reply_markup(player_markup(state.paused, state.loop > 0))
    except Exception:
        pass


def _plain(html_text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", html_text))
