import os

from pyrogram import Client
from pyrogram.types import Message

import config
from MusicBot.core import player, queue, youtube
from MusicBot.core.queue import Track
from MusicBot.utils.decorators import group_only, is_admin
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


async def _play(client: Client, message: Message, video: bool, force: bool = False):
    chat_id = message.chat.id
    replied = message.reply_to_message
    query = message.text.split(None, 1)[1].strip() if len(message.command) > 1 else ""

    if force and not await is_admin(chat_id, message.from_user.id if message.from_user else None):
        return await message.reply_text("🔒 Only admins can force-play.")

    if not query and not (replied and replied.media):
        return await message.reply_text(
            "<b>Usage:</b>\n"
            f"<code>/{message.command[0]} song name</code>\n"
            f"<code>/{message.command[0]} YouTube link</code>\n"
            "or reply to an audio / video file."
        )

    status = await message.reply_text("🔎 <b>Searching…</b>")
    try:
        await player.ensure_assistant(chat_id)

        tracks: list[Track] = []
        if not query and replied and replied.media:
            await status.edit_text("📥 <b>Downloading file…</b>")
            track = await _track_from_file(message, replied, video)
            if track is None:
                return await status.edit_text("❌ Reply to an audio, voice or video file.")
            tracks.append(track)
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
            await status.edit_text("⚡ <b>Force playing…</b>")
            await player.skip(chat_id)
            for t in tracks:
                await player.enqueue(chat_id, t)
            return await status.delete()

        if not state.current:
            await status.edit_text(
                f"📥 <b>Preparing</b> {esc(tracks[0].title, 45)}…\n<i>Buffering for lag-free playback</i>"
            )
        first_pos = await player.enqueue(chat_id, tracks[0])
        for t in tracks[1:]:
            try:
                await player.enqueue(chat_id, t)
            except player.PlayerError:
                break

        if len(tracks) > 1:
            return await status.edit_text(
                f"📜 <b>Added {len(tracks)} tracks</b> from playlist to the queue.\n"
                f"👤 By: {_requester(message)}"
            )
        if first_pos == 0:
            return await status.delete()  # now-playing card was sent by the player
        t = tracks[0]
        await status.edit_text(
            f"<b>➕ Added to queue at #{first_pos}</b>\n\n"
            f"🎵 <a href=\"{t.link}\">{esc(t.title)}</a>\n"
            f"⏱ <code>{fmt_time(t.duration)}</code>  •  👤 {t.requested_by}",
            disable_web_page_preview=True,
        )
    except (player.PlayerError, youtube.YouTubeError) as e:
        await status.edit_text(str(e) if isinstance(e, player.PlayerError) else f"❌ <b>YouTube error:</b> <code>{esc(str(e), 300)}</code>")
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
