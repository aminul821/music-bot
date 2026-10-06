"""YouTube search & download helpers built on yt-dlp."""
import asyncio
import glob
import logging
import os
import re

from yt_dlp import YoutubeDL

import config

YT_LINK = re.compile(r"(https?://)?(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/\S+")

LOGGER = logging.getLogger("MusicBot.youtube")

# Player clients tried in order when YouTube refuses a download (HTTP 403 etc).
# None = yt-dlp's own default choice.
FALLBACK_CLIENTS: list[list[str] | None] = [
    None,
    ["tv_simply", "web_safari"],
    ["android_vr"],
    ["mweb"],
    ["tv", "web_embedded"],
]
if config.YT_CLIENTS:
    FALLBACK_CLIENTS.insert(0, config.YT_CLIENTS)

VIDEO_HEIGHTS = {"4k": 2160, "2k": 1440, "1080": 1080, "720": 720, "480": 480, "360": 360}

os.makedirs(config.DOWNLOAD_DIR, exist_ok=True)


BOT_CHECK_HELP = (
    "🤖 YouTube is blocking this server (\"Sign in to confirm you're not a bot\").\n"
    "Fix: export YouTube <b>cookies.txt</b> from a logged-in browser, send it to me and "
    "reply to it with <code>/setcookies</code> (owner/sudo only). "
    "A residential <code>YT_PROXY</code> also works."
)


class YouTubeError(Exception):
    pass


class _QuietLogger:
    """Keep yt-dlp from printing to the console; we log failures ourselves."""

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


def _is_bot_check(error: Exception | None) -> bool:
    text = str(error or "")
    return "Sign in to confirm" in text or "not a bot" in text


def _base_opts(clients: list[str] | None = None) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "noplaylist": True,
        "concurrent_fragment_downloads": 8,
        "retries": 5,
        "fragment_retries": 5,
        # Small HTTP chunks avoid YouTube throttling/403s on long downloads.
        "http_chunk_size": 10 * 1024 * 1024,
        # YouTube needs a JS runtime to unlock most formats (deno is preferred).
        "js_runtimes": {"deno": {}, "node": {}, "bun": {}},
        "remote_components": ["ejs:github"],
        "logger": _QuietLogger(),
    }
    if config.YT_PROXY:
        opts["proxy"] = config.YT_PROXY
    if clients:
        opts["extractor_args"] = {"youtube": {"player_client": clients}}
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
        if _is_bot_check(e):
            raise YouTubeError(BOT_CHECK_HELP) from e
        raise YouTubeError(str(e).splitlines()[0][:300]) from e


def _video_height() -> int:
    return VIDEO_HEIGHTS.get(config.VIDEO_QUALITY, 720)


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

    last_error: Exception | None = None
    for clients in FALLBACK_CLIENTS:
        opts = _base_opts(clients)
        opts.update(
            format=fmt,
            outtmpl=os.path.join(config.DOWNLOAD_DIR, f"{name}.%(ext)s"),
            merge_output_format="mkv",
        )
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=True)
                path = info.get("requested_downloads", [{}])[0].get("filepath") or ydl.prepare_filename(info)
            if os.path.isfile(path):
                return path
            last_error = YouTubeError("Download failed.")
        except Exception as e:
            last_error = e
            LOGGER.warning("Download of %s failed with clients=%s: %s", vidid, clients or "default", str(e).splitlines()[0])
        for leftover in glob.glob(os.path.join(config.DOWNLOAD_DIR, f"{name}.*")):
            try:
                os.remove(leftover)
            except OSError:
                pass
    if _is_bot_check(last_error):
        raise YouTubeError(BOT_CHECK_HELP) from last_error
    raise YouTubeError(
        "YouTube blocked the download (HTTP 403). Install Deno, update yt-dlp, "
        "or add cookies with /setcookies — see README › Troubleshooting."
    ) from last_error


def _live_url(link: str, video: bool) -> str:
    last_error: Exception | None = None
    for clients in FALLBACK_CLIENTS:
        opts = _base_opts(clients)
        opts["format"] = f"best[height<={_video_height()}]/best" if video else "bestaudio/best"
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=False)
            if info.get("url"):
                return info["url"]
        except Exception as e:
            last_error = e
    if _is_bot_check(last_error):
        raise YouTubeError(BOT_CHECK_HELP) from last_error
    raise YouTubeError("Could not get live stream URL.") from last_error


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
