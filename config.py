"""Bot configuration. Values are read from environment variables / a .env file."""
import os

from dotenv import load_dotenv

load_dotenv()


def _int_list(value: str) -> list[int]:
    return [int(x) for x in value.replace(",", " ").split() if x.strip().lstrip("-").isdigit()]


def _bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


# --- Required ------------------------------------------------------------
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
# Pyrogram string session of the assistant account that joins voice chats.
STRING_SESSION = os.getenv("STRING_SESSION", "")

# --- Branding / private group ---------------------------------------------
BOT_NAME = os.getenv("BOT_NAME", "🥰🥳❤️ Mad Family ❤️🥰🥳 Music Bot")
# Group id(s) the bot is allowed in (send /id in the group to get it). Empty = any group.
ALLOWED_CHATS = set(_int_list(os.getenv("ALLOWED_CHATS", "")))
# Invite link of your group, shown on /start.
GROUP_LINK = os.getenv("GROUP_LINK", "")

# --- Optional ------------------------------------------------------------
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
SUDO_USERS = set(_int_list(os.getenv("SUDO_USERS", ""))) | ({OWNER_ID} if OWNER_ID else set())

# Max allowed track length in minutes (0 = unlimited).
DURATION_LIMIT = int(os.getenv("DURATION_LIMIT", "180"))
# Max tracks waiting in one chat's queue.
QUEUE_LIMIT = int(os.getenv("QUEUE_LIMIT", "50"))

# Audio quality: high (48 kHz stereo, Telegram's native rate — best), studio (96 kHz), medium, low.
AUDIO_QUALITY = os.getenv("AUDIO_QUALITY", "high").lower()
# Video quality for /vplay: 4k, 2k, 1080, 720, 480, 360.
VIDEO_QUALITY = os.getenv("VIDEO_QUALITY", "1080").lower()

# Only chat admins (and sudo users) can control playback when enabled.
ADMIN_ONLY = _bool(os.getenv("ADMIN_ONLY", "true"))

# Path to a Netscape-format cookies.txt for yt-dlp (helps with YouTube rate limits).
COOKIES_FILE = os.getenv("COOKIES_FILE", "") or ("cookies.txt" if os.path.isfile("cookies.txt") else "")
# Optional proxy for YouTube, e.g. http://user:pass@host:port or socks5://host:port
YT_PROXY = os.getenv("YT_PROXY", "")
# Optional comma-separated yt-dlp YouTube player clients to try first, e.g. "tv_simply,web_safari".
YT_CLIENTS = [c.strip() for c in os.getenv("YT_CLIENTS", "").split(",") if c.strip()]
DOWNLOAD_DIR = os.path.abspath(os.getenv("DOWNLOAD_DIR", "downloads"))

SUPPORT_CHAT = os.getenv("SUPPORT_CHAT", "")
UPDATES_CHANNEL = os.getenv("UPDATES_CHANNEL", "")
START_IMG = os.getenv("START_IMG", "")

# --- Touch Grass (open-weight AI, runs on your own machine via Ollama) ------
# Ollama server that hosts the open-weight model. Photos and plans never leave it.
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
# Any Ollama model. A vision model (gemma3, qwen2.5vl, llava…) also checks /touched photos.
GRASS_MODEL = os.getenv("GRASS_MODEL", "gemma3:4b")
# Nudge the group to go outside after this many hours of non-stop voice chat (0 = off).
GRASS_NUDGE_HOURS = float(os.getenv("GRASS_NUDGE_HOURS", "3"))
# How far to look for parks, trails and viewpoints, in metres.
GRASS_RADIUS = int(os.getenv("GRASS_RADIUS", "3000"))
