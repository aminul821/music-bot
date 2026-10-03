"""YouTube search & download helpers built on yt-dlp."""
import asyncio
import glob
import os
import re

from yt_dlp import YoutubeDL

import config

YT_LINK = re.compile(r"(https?://)?(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/\S+")

VIDEO_HEIGHTS = {"4k": 2160, "2k": 1440, "1080": 1080, "720": 720, "480": 480, "360": 360}

os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)


class YouTubeError(Exception):
    pass


def _base_opts() -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "noplaylist": True,
        "concurrent_fragment_downloads": 8,
        "retries": 5,
        "fragment_retries": 5,
    }
    if config.COOKIES_FILE and os.path.isfile(config.COOKIES_FILE):
        opts["cookiefile"] = config.COOKIES_FILE
    return opts


def is_youtube(text: str) -> bool:
    return bool(YT_LINK.match(text.strip()))


def _thumb(entry: dict) -> str | None:
    if entry.get("id"):
        return f"https://i.ytimg.com/vi/{entry['id']}/hqdefault.jpg"
    return entry.get("thumbnail")


def _normalize(entry: dict) -> dict:
    vid = entry.get("id")
    return {
        "id": vid,
        "title": entry.get("title") or "Unknown",
        "duration": int(entry.get("duration") or 0),
        "link": entry.get("webpage_url") or (f"https://www.youtube.com/watch?v={vid}" if vid else entry.get("url")),
        "thumb": _thumb(entry),
        "is_live": bool(entry.get("is_live") or entry.get("live_status") == "is_live"),
        "channel": entry.get("channel") or entry.get("uploader") or "",
    }


def _extract(query: str) -> list[dict]:
    query = query.strip()
    opts = _base_opts()
    if is_youtube(query) and "list=" in query and "watch?v=" not in query:
        # Playlist link: fetch entries quickly without resolving each video.
        opts.update(noplaylist=False, extract_flat="in_playlist", playlistend=config.QUEUE_LIMIT)
        target = query
    elif is_youtube(query):
        target = query
    else:
        opts["extract_flat"] = "in_playlist"
        target = f"ytsearch1:{query}"

    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(target, download=False)
    if not info:
        raise YouTubeError("Nothing found.")
    entries = info.get("entries")
    if entries is None:
        return [_normalize(info)]
    results = [_normalize(e) for e in entries if e and e.get("id")]
    if not results:
        raise YouTubeError("Nothing found.")
    return results


async def search(query: str) -> list[dict]:
    """Resolve a search query, video link or playlist link into track info dicts."""
    try:
        return await asyncio.to_thread(_extract, query)
    except YouTubeError:
        raise
    except Exception as e:  # yt-dlp raises many different error types
        raise YouTubeError(str(e).splitlines()[0][:300]) from e


def _video_height() -> int:
    return VIDEO_HEIGHTS.get(config.VIDEO_QUALITY, 1080)


def _download(link: str, vidid: str, video: bool) -> str:
    if video:
        h = _video_height()
        name = f"{vidid}_v{h}"
        fmt = (
            f"bestvideo[height<={h}][vcodec~='^(avc1|vp0?9)']+bestaudio"
            f"/bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"
        )
    else:
        name = f"{vidid}_a"
        fmt = "bestaudio[acodec=opus]/bestaudio[ext=m4a]/bestaudio/best"

    cached = [p for p in glob.glob(os.path.join(config.DOWNLOAD_DIR, f"{name}.*")) if not p.endswith(".part")]
    if cached:
        return cached[0]

    opts = _base_opts()
    opts.update(
        format=fmt,
        outtmpl=os.path.join(config.DOWNLOAD_DIR, f"{name}.%(ext)s"),
        merge_output_format="mkv",
    )
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(link, download=True)
        path = info.get("requested_downloads", [{}])[0].get("filepath") or ydl.prepare_filename(info)
    if not os.path.isfile(path):
        raise YouTubeError("Download failed.")
    return path


def _live_url(link: str, video: bool) -> str:
    opts = _base_opts()
    opts["format"] = f"best[height<={_video_height()}]/best" if video else "bestaudio/best"
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(link, download=False)
    url = info.get("url")
    if not url:
        raise YouTubeError("Could not get live stream URL.")
    return url


async def download(link: str, vidid: str, video: bool = False, live: bool = False) -> str:
    """Download a track (or resolve a live stream URL) and return a playable path."""
    try:
        if live:
            return await asyncio.to_thread(_live_url, link, video)
        return await asyncio.to_thread(_download, link, vidid, video)
    except YouTubeError:
        raise
    except Exception as e:
        raise YouTubeError(str(e).splitlines()[0][:300]) from e
