import html
import re

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from MusicBot.core import player, queue
from MusicBot.utils.buttons import close_markup
from MusicBot.utils.decorators import callback_can_control, control_only, group_only
from MusicBot.utils.filters import command
from MusicBot.utils.formatters import esc, fmt_pos, fmt_time, mention, parse_time, progress_bar


def _by(message: Message) -> str:
    return mention(message.from_user) if message.from_user else "Admin"


def queue_text(chat_id: int, limit: int = 15) -> str:
    state = queue.get(chat_id)
    if not state.tracks:
        return "📭 <b>ᴛʜᴇ ǫᴜᴇᴜᴇ ɪs ᴇᴍᴘᴛʏ</b>\n<i>Add something with</i> <code>/play</code>"
    cur = state.current
    lines = [
        "╭─❰ 📜 <b>ǫᴜᴇᴜᴇ</b> ❱",
        f"│ ▶️ <b>{esc(cur.title, 45)}</b>",
        f"│    <code>{fmt_pos(cur.elapsed())} / {fmt_time(cur.duration)}</code> • {cur.requested_by}",
    ]
    upcoming = state.tracks[1:]
    if upcoming:
        lines.append("│")
        for i, t in enumerate(upcoming[:limit], start=1):
            icon = "📺" if t.video else "🎵"
            lines.append(f"│ <b>{i:02d}.</b> {icon} {esc(t.title, 40)} <code>{fmt_time(t.duration)}</code>")
        if len(upcoming) > limit:
            lines.append(f"│ <i>…ᴀɴᴅ {len(upcoming) - limit} ᴍᴏʀᴇ</i>")
        total = sum(t.duration for t in upcoming)
        lines.append(f"╰─ 🎶 <b>{len(upcoming)}</b> ᴜᴘᴄᴏᴍɪɴɢ • ⏱ <code>{fmt_time(total)}</code>")
    else:
        lines.append("╰─ <i>ɴᴏᴛʜɪɴɢ ᴜᴘ ɴᴇxᴛ</i>")
    if state.loop:
        lines.append(f"🔂 ʟᴏᴏᴘ: <b>{state.loop}</b> more time(s)")
    return "\n".join(lines)


def np_text(chat_id: int) -> str | None:
    state = queue.get(chat_id)
    t = state.current
    if not t:
        return None
    elapsed = t.elapsed()
    status = "⏸ ᴘᴀᴜsᴇᴅ" if state.paused else "▶️ ᴘʟᴀʏɪɴɢ"
    return (
        f"<b>✦ {status} ✦</b>  {'📺 ᴠɪᴅᴇᴏ' if t.video else '🎧 ᴀᴜᴅɪᴏ'}\n\n"
        f"<blockquote>🎵 <b>{esc(t.title)}</b></blockquote>\n"
        f"<code>{fmt_pos(elapsed)}</code> {progress_bar(elapsed, t.duration)} <code>{fmt_time(t.duration)}</code>\n\n"
        f"🔊 ᴠᴏʟᴜᴍᴇ ➜ <b>{state.volume}%</b>\n"
        f"🔁 ʟᴏᴏᴘ ➜ <b>{state.loop or 'ᴏғғ'}</b>\n"
        f"👤 ʀᴇǫᴜᴇsᴛᴇᴅ ➜ {t.requested_by}"
    )


async def _require_playing(message: Message) -> bool:
    if not queue.get(message.chat.id).current:
        await message.reply_text("🔇 <b>ɴᴏᴛʜɪɴɢ ɪs ᴘʟᴀʏɪɴɢ</b>\n<i>Start with</i> <code>/play song name</code>")
        return False
    return True


@Client.on_message(command("pause"))
@control_only
async def pause_cmd(client: Client, message: Message):
    if not await _require_playing(message):
        return
    if await player.pause(message.chat.id):
        await message.reply_text(f"⏸ <b>ᴘᴀᴜsᴇᴅ</b> ➜ ʙʏ {_by(message)}")
    else:
        await message.reply_text("ℹ️ Already paused.")


@Client.on_message(command("resume"))
@control_only
async def resume_cmd(client: Client, message: Message):
    if not await _require_playing(message):
        return
    if await player.resume(message.chat.id):
        await message.reply_text(f"▶️ <b>ʀᴇsᴜᴍᴇᴅ</b> ➜ ʙʏ {_by(message)}")
    else:
        await message.reply_text("ℹ️ Already playing.")


@Client.on_message(command("skip", "next"))
@control_only
async def skip_cmd(client: Client, message: Message):
    if not await _require_playing(message):
        return
    nxt = await player.skip(message.chat.id)
    if nxt is None:
        await message.reply_text(f"⏭ <b>sᴋɪᴘᴘᴇᴅ</b> ➜ ʙʏ {_by(message)}\n📭 <i>queue is now empty</i>")
    else:
        await message.reply_text(f"⏭ <b>sᴋɪᴘᴘᴇᴅ</b> ➜ ʙʏ {_by(message)}")


@Client.on_message(command("stop", "end"))
@control_only
async def stop_cmd(client: Client, message: Message):
    await player.stop(message.chat.id)
    await message.reply_text(f"⏹ <b>sᴛᴏᴘᴘᴇᴅ</b> ➜ ʙʏ {_by(message)}\n👋 <i>queue cleared, left the voice chat</i>")


@Client.on_message(command("loop", "repeat"))
@control_only
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
        f"🔂 <b>ʟᴏᴏᴘ</b> ➜ <b>{state.loop}</b> time(s)" if state.loop else "🔁 <b>ʟᴏᴏᴘ ᴅɪsᴀʙʟᴇᴅ</b>"
    )


@Client.on_message(command("shuffle"))
@control_only
async def shuffle_cmd(client: Client, message: Message):
    state = queue.get(message.chat.id)
    if len(state.tracks) < 3:
        return await message.reply_text("ℹ️ Need at least 2 upcoming tracks to shuffle.")
    state.shuffle()
    await message.reply_text("🔀 <b>ǫᴜᴇᴜᴇ sʜᴜғғʟᴇᴅ!</b>\n\n" + queue_text(message.chat.id, 10), reply_markup=close_markup())


@Client.on_message(command("remove"))
@control_only
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
@control_only
async def clear_cmd(client: Client, message: Message):
    state = queue.get(message.chat.id)
    removed = state.tracks[1:]
    del state.tracks[1:]
    for t in removed:
        if t.download and not t.download.done():
            t.download.cancel()
    await message.reply_text(f"🧹 Cleared <b>{len(removed)}</b> upcoming track(s).")


@Client.on_message(command("seek"))
@control_only
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
    await message.reply_text(f"⏩ <b>sᴇᴇᴋᴇᴅ</b> ➜ <code>{fmt_pos(target)}</code>")


@Client.on_message(command("volume", "vol"))
@control_only
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
    await message.reply_text(f"🔊 <b>ᴠᴏʟᴜᴍᴇ</b> ➜ <b>{vol}%</b>")


@Client.on_message(command("queue", "q"))
@group_only
async def queue_cmd(client: Client, message: Message):
    await message.reply_text(queue_text(message.chat.id), reply_markup=close_markup(), disable_web_page_preview=True)


@Client.on_message(command("np", "now", "nowplaying", "current"))
@group_only
async def np_cmd(client: Client, message: Message):
    text = np_text(message.chat.id)
    if not text:
        return await message.reply_text("🔇 <b>ɴᴏᴛʜɪɴɢ ɪs ᴘʟᴀʏɪɴɢ</b>\n<i>Start with</i> <code>/play song name</code>")
    await message.reply_text(text, reply_markup=player.current_markup(message.chat.id))


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
    if action == "np":
        t = state.current
        return await query.answer(
            f"🎵 {t.title[:80]}\n⏱ {fmt_pos(t.elapsed())} / {fmt_time(t.duration)}\n🔊 {state.volume}%",
            show_alert=True,
        )
    if not await callback_can_control(query):
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
        elif action == "shuffle":
            if len(state.tracks) < 3:
                return await query.answer("Need 2+ upcoming tracks to shuffle.", show_alert=True)
            state.shuffle()
            await query.answer("🔀 Queue shuffled")
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
        await query.message.edit_reply_markup(player.current_markup(chat_id))
    except Exception:
        pass


def _plain(html_text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", html_text))
