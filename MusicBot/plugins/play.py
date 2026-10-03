import asyncio
import json
import os
import re
from urllib.parse import unquote, urlparse

from pyrogram import Client
from pyrogram.types import Message

import config
from MusicBot.core import player, queue, youtube
from MusicBot.core.queue import Track
from MusicBot.utils.decorators import can_play, group_only, is_admin
from MusicBot.utils.filters import command
from MusicBot.utils.formatters import esc, fmt_time, mention


def _requester(message: Message) -> str:
    if message.from_user:
        return mention(message.from_user)
    if message.sender_chat:
        return esc(message.sender_chat.title or "Anonymous", 30)
    return "Anonymous"


async def _track_from_file(message: Message, media_msg: Message, video: bool) -> Track | None:
    media = media_msg.audio or media_msg.voice or media_msg.video or media_msg.document
    if media_msg.video or (media_msg.document and (media_msg.document.mime_type or "").startswith("video")):
        pass  # keep the requested mode: /play streams only its audio, /vplay the video
    elif media_msg.audio or media_msg.voice or (
        media_msg.document and (media_msg.document.mime_type or "").startswith("audio")
    ):
        video = False
    else:
        return None
    duration = int(getattr(media, "duration", 0) or 0)
    if config.DURATION_LIMIT and duration > config.DURATION_LIMIT * 60:
        raise player.PlayerError(f"⏳ Tracks longer than {config.DURATION_LIMIT} min aren't allowed.")
    title = (
        getattr(media, "title", None)
        or getattr(media, "file_name", None)
        or ("Voice message" if media_msg.voice else "Telegram file")
    )
    ext = os.path.splitext(getattr(media, "file_name", "") or "")[1] or (".ogg" if media_msg.voice else ".mp4" if video else ".mp3")
    path = os.path.join(config.DOWNLOAD_DIR, f"tg_{media.file_unique_id}{ext}")
    if not os.path.isfile(path):
        path = await media_msg.download(file_name=os.path.abspath(path))
    return Track(
        title=title,
        duration=duration or 1,
        source=path,
        requested_by=_requester(message),
        video=video,
        path=path,
        link=media_msg.link,
    )


URL_RE = re.compile(r"^https?://\S+$")


async def _probe_duration(url: str) -> int:
    """Duration of a direct media link in seconds (0 = live/unknown)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", url,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        return int(float(json.loads(out or b"{}").get("format", {}).get("duration") or 0))
    except Exception:
        return 0


async def _track_from_url(message: Message, url: str, video: bool) -> Track:
    name = unquote(os.path.basename(urlparse(url).path)) or urlparse(url).netloc
    duration = await _probe_duration(url)
    return Track(
        title=name[:80] or "Direct stream",
        duration=duration,
        source=url,
        requested_by=_requester(message),
        video=video,
        path=url,
        link=url,
    )


async def _play(client: Client, message: Message, video: bool, force: bool = False):
    chat_id = message.chat.id
    replied = message.reply_to_message
    query = message.text.split(None, 1)[1].strip() if len(message.command) > 1 else ""

    user_id = message.from_user.id if message.from_user else None
    anon_admin = bool(message.sender_chat and message.sender_chat.id == chat_id)
    if force and not anon_admin and not await is_admin(chat_id, user_id):
        return await message.reply_text("🛡 ᴏɴʟʏ ᴀᴅᴍɪɴs ᴄᴀɴ ғᴏʀᴄᴇ-ᴘʟᴀʏ.")
    if not anon_admin and not await can_play(chat_id, user_id):
        return await message.reply_text(
            "🔒 <b>ᴘʟᴀʏ ᴍᴏᴅᴇ: ᴀᴅᴍɪɴs</b>\nOnly admins and approved users can add songs here."
        )

    if not query and not (replied and replied.media):
        cmd = message.command[0]
        return await message.reply_text(
            f"╭─❰ {'📺' if video else '🎵'} <b>ʜᴏᴡ ᴛᴏ ᴜsᴇ</b> ❱\n"
            f"│ <code>/{cmd} song name</code>\n"
            f"│ <code>/{cmd} YouTube link / playlist</code>\n"
            f"│ <code>/{cmd} https://direct/link.mp4</code>\n"
            f"╰─ or reply to {'a video' if video else 'an audio'} file"
        )

    status = await message.reply_text("🔎 <b>sᴇᴀʀᴄʜɪɴɢ…</b>")
    try:
        await player.ensure_assistant(chat_id)

        tracks: list[Track] = []
        if not query and replied and replied.media:
            await status.edit_text("📥 <b>ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ғɪʟᴇ…</b>")
            track = await _track_from_file(message, replied, video)
            if track is None:
                return await status.edit_text("❌ Reply to an audio, voice or video file.")
            tracks.append(track)
        elif URL_RE.match(query) and not youtube.is_youtube(query):
            await status.edit_text("🔗 <b>ᴏᴘᴇɴɪɴɢ sᴛʀᴇᴀᴍ…</b>")
            tracks.append(await _track_from_url(message, query, video))
        else:
            results = await youtube.search(query)
            for info in results:
                if (
                    config.DURATION_LIMIT
                    and info["duration"] > config.DURATION_LIMIT * 60
                    and len(results) == 1
                ):
                    return await status.edit_text(
                        f"⏳ <b>{esc(info['title'])}</b> is {fmt_time(info['duration'])} long.\n"
                        f"Limit is {config.DURATION_LIMIT} minutes."
                    )
                if config.DURATION_LIMIT and info["duration"] > config.DURATION_LIMIT * 60:
                    continue
                tracks.append(
                    Track(
                        title=info["title"],
                        duration=0 if info["is_live"] else info["duration"],
                        source=info["link"],
                        requested_by=_requester(message),
                        video=video,
                        vidid=info["id"],
                        thumb=info["thumb"],
                        link=info["link"],
                    )
                )
        if not tracks:
            return await status.edit_text("❌ No playable tracks found.")

        state = queue.get(chat_id)
        if force and state.current:
            # Put the new track right after the current one, then skip to it.
            state.tracks[1:1] = tracks[:1]
            tracks = tracks[1:]
            await status.edit_text("⚡ <b>ғᴏʀᴄᴇ ᴘʟᴀʏɪɴɢ…</b>")
            await player.skip(chat_id)
            for t in tracks:
                await player.enqueue(chat_id, t)
            return await status.delete()

        if not state.current:
            await status.edit_text(
                f"⚡ <b>ᴘʀᴇᴘᴀʀɪɴɢ</b> ➜ <i>{esc(tracks[0].title, 45)}</i>\n"
                "<code>▰▰▰▰▱▱▱▱</code> <i>buffering for smooth playback…</i>"
            )
        first_pos = await player.enqueue(chat_id, tracks[0])
        for t in tracks[1:]:
            try:
                await player.enqueue(chat_id, t)
            except player.PlayerError:
                break

        if len(tracks) > 1:
            return await status.edit_text(
                "╭─❰ 📜 <b>ᴘʟᴀʏʟɪsᴛ ᴀᴅᴅᴇᴅ</b> ❱\n"
                f"│ 🎶 <b>{len(tracks)}</b> tracks queued\n"
                f"╰─ 👤 {_requester(message)}"
            )
        if first_pos == 0:
            return await status.delete()  # now-playing card was sent by the player
        t = tracks[0]
        await status.edit_text(
            f"╭─❰ ➕ <b>ᴀᴅᴅᴇᴅ ᴛᴏ ǫᴜᴇᴜᴇ</b> • <code>#{first_pos}</code> ❱\n"
            f"│ {'📺' if t.video else '🎵'} <a href=\"{t.link}\">{esc(t.title, 45)}</a>\n"
            f"│ ⏳ <code>{fmt_time(t.duration)}</code>\n"
            f"╰─ 👤 {t.requested_by}",
            disable_web_page_preview=True,
        )
    except (player.PlayerError, youtube.YouTubeError) as e:
        if isinstance(e, player.PlayerError) or str(e) == youtube.BOT_CHECK_HELP:
            await status.edit_text(str(e))
        else:
            await status.edit_text(f"❌ <b>YouTube error:</b> <code>{esc(str(e), 300)}</code>")
    except Exception as e:
        await status.edit_text(f"❌ <b>Failed to play:</b> <code>{esc(f'{type(e).__name__}: {e}', 300)}</code>")


@Client.on_message(command("play", "p"))
@group_only
async def play_cmd(client: Client, message: Message):
    await _play(client, message, video=False)


@Client.on_message(command("vplay", "vp", "video"))
@group_only
async def vplay_cmd(client: Client, message: Message):
    await _play(client, message, video=True)


@Client.on_message(command("playforce", "forceplay"))
@group_only
async def playforce_cmd(client: Client, message: Message):
    await _play(client, message, video=False, force=True)


@Client.on_message(command("vplayforce", "vforceplay"))
@group_only
async def vplayforce_cmd(client: Client, message: Message):
    await _play(client, message, video=True, force=True)


@Client.on_message(command("stream"))
@group_only
async def stream_cmd(client: Client, message: Message):
    """Audio from any direct link / m3u8 / radio stream (also works with YouTube)."""
    await _play(client, message, video=False)


@Client.on_message(command("vstream"))
@group_only
async def vstream_cmd(client: Client, message: Message):
    """Video from any direct link / m3u8 / live stream (also works with YouTube)."""
    await _play(client, message, video=True)
