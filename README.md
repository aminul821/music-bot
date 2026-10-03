# 🥰🥳❤️ Mad Family ❤️🥰🥳 Music Bot

The private music bot of the **Mad Family** Telegram group. It downloads songs from
YouTube and plays them in the group voice chat in high quality. It uses a **bot token**
for commands and buttons, and an **assistant account** (Pyrogram string session) that
joins the voice chat.

## ✨ Features

- 🎧 **Hi-fi audio** at 48 kHz stereo, Telegram's native voice chat rate (configurable)
- 📺 **Video streaming** up to 4K with `/vplay`
- ⚡ **Smooth playback**: tracks are fully downloaded before they play, and the next
  track downloads in the background so there's no gap between songs
- 🔎 Play by song name, YouTube link, **YouTube playlist**, or by replying to an audio/video file
- 📜 Queue, loop, shuffle, seek, volume, remove and clear
- 🎛 Inline control panel (pause/resume, ±10s, skip, stop, loop, volume, queue)
- 🤖 The assistant joins your group automatically
- 🎙 Starts the voice chat if it's off. If the assistant lacks rights, the bot promotes it
  to voice chat admin (give the bot **Add New Admins** for this)
- 🔒 Admin-only controls (needs *Manage Video Chats*), plus sudo users

## 📋 Commands

| Command | Description |
|---|---|
| `/play <name/link>` | Play audio (or reply to an audio file) |
| `/vplay <name/link>` | Play video (or reply to a video file) |
| `/stream <url>` | Play any direct audio link, radio or m3u8 |
| `/vstream <url>` | Play any direct video link or live stream |
| `/playforce`, `/vplayforce` | Skip the current track and play this one now (admins) |
| `/pause` / `/resume` | Pause or resume |
| `/skip` | Next track |
| `/stop` / `/end` | Clear the queue and leave the voice chat |
| `/seek 1:30`, `/seek +30` | Jump to a position |
| `/volume 1-200` | Set volume |
| `/loop [1-10/off]` | Repeat the current track |
| `/shuffle` | Shuffle upcoming tracks |
| `/queue` | Show the queue |
| `/np` | Now playing, with a progress bar |
| `/remove <pos>` / `/clear` | Remove one upcoming track, or all of them |
| `/ping` | Latency and uptime |
| `/id` | Show the chat ID and your user ID |
| `/approve` / `/unapprove` | Let a user control playback (admins; reply or `@user`) |
| `/approved`, `/unapproveall` | List or clear approved users (admins) |
| `/adminmode on\|off` | Only admins and approved users control playback (admins) |
| `/playmode everyone\|admins` | Who can add songs (admins) |
| `/settings` | Settings panel with toggle buttons (admins) |
| `/userbotjoin`, `/userbotleave` | Add or remove the assistant (admins) |
| `/reload` | Refresh the cached admin list (admins) |
| `/stats` | Active chats (sudo only) |
| `/setcookies` | Reply to a `cookies.txt` to update YouTube cookies (sudo only) |

Commands work with the `/`, `!`, `.` and `;` prefixes (e.g. `;approve`, `.skip`).

**Who can do what:** sudo users can do everything. Chat admins with *Manage Video
Chats* can use the admin commands. Approved users can use the playback controls even
when admin mode is on. Everyone else can `/play` (unless play mode is `admins`) and
view `/queue` and `/np`. Settings and approvals are saved in `data/db.json`.

## ⚙️ Setup

1. Get `API_ID` and `API_HASH` from <https://my.telegram.org>.
2. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
3. Generate the assistant's string session. Use a **separate user account**, not the bot:
   ```bash
   pip install -r requirements.txt
   python generate_session.py
   ```
4. Copy `.env.example` to `.env` and fill in the values.
5. Install **ffmpeg** and **Deno** (YouTube needs a JS runtime), then run the bot:
   ```bash
   sudo apt install -y ffmpeg unzip
   curl -fsSL https://deno.land/install.sh | sh   # then restart your shell
   python -m MusicBot
   ```
   Or use Docker:
   ```bash
   docker build -t music-bot .
   docker run -d --env-file .env --name music-bot music-bot
   ```
6. Add the bot to the Mad Family group as an admin with **Manage Video Chats**,
   **Invite Users**, **Delete Messages** and **Add New Admins**. The last one lets it
   promote the assistant so the assistant can start the voice chat. Then send `/play song name`.
7. **Lock it to your group:** send `/id` in the group. Put that number in `.env` as
   `ALLOWED_CHATS=-100...` and restart. In any other group, the bot will say it's
   private and leave.

### Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `API_ID`, `API_HASH` | — | Telegram API credentials (**required**) |
| `BOT_TOKEN` | — | Bot token from BotFather (**required**) |
| `STRING_SESSION` | — | Pyrogram string session of the assistant (**required**) |
| `BOT_NAME` | `🥰🥳❤️ Mad Family ❤️🥰🥳 Music Bot` | Name shown in the bot's messages |
| `ALLOWED_CHATS` | — | Group ID(s) the bot works in (get it with `/id`); other groups are left |
| `GROUP_LINK` | — | Mad Family invite link, shown as a button on `/start` |
| `OWNER_ID`, `SUDO_USERS` | — | User IDs with full control |
| `AUDIO_QUALITY` | `high` | `high` (48 kHz, recommended), `studio` (96 kHz), `medium` or `low` |
| `VIDEO_QUALITY` | `1080` | `4k`, `2k`, `1080`, `720`, `480` or `360` |
| `DURATION_LIMIT` | `180` | Longest allowed track, in minutes (`0` = no limit) |
| `QUEUE_LIMIT` | `50` | Maximum tracks in one queue |
| `ADMIN_ONLY` | `true` | Only admins can control playback |
| `COOKIES_FILE` | — | YouTube `cookies.txt` (helps if YouTube blocks your server) |
| `YT_PROXY` | — | Proxy for YouTube requests (residential works best) |
| `YT_CLIENTS` | — | yt-dlp player clients to try first, e.g. `tv_simply,web_safari` |
| `SUPPORT_CHAT`, `UPDATES_CHANNEL`, `START_IMG` | — | Optional links and image for `/start` |

> **Tip:** 4K video uses a lot of CPU and bandwidth. On a small VPS, use `VIDEO_QUALITY=720`.

> ⚠️ Never share your `STRING_SESSION`. It gives full access to the assistant account.

## 🔁 Run 24/7 (without keeping the terminal open)

If you start the bot with `python -m MusicBot`, it stops when you close the terminal.
Install it as a service instead:

```bash
cd ~/music-bot
bash deploy/install-service.sh
```

The bot then keeps running after you log out, restarts automatically if it crashes,
and starts again when the server reboots.

| Task | Command |
|---|---|
| Live logs | `sudo journalctl -u musicbot -f` |
| Restart (e.g. after `git pull`) | `sudo systemctl restart musicbot` |
| Stop / start | `sudo systemctl stop musicbot` / `sudo systemctl start musicbot` |
| Status | `sudo systemctl status musicbot` |

## 🛠 Troubleshooting

**`Sign in to confirm you're not a bot`** or **`HTTP Error 403: Forbidden`**

YouTube blocks most cloud/VPS IP addresses (Azure, AWS, GCP…). You need one of these:

1. **Cookies (easiest).** In a browser, log into YouTube with a **spare account**.
   Export `cookies.txt` with the *"Get cookies.txt LOCALLY"* extension.
   Then either:
   - send the file to the bot and reply to it with `/setcookies` (owner/sudo only), or
   - upload it to the bot folder as `cookies.txt`. It's picked up automatically, or you
     can point `COOKIES_FILE` at it.

   Cookies expire from time to time. If the error comes back, export them again.
2. **PO token provider** (works well together with cookies):
   ```bash
   docker run -d --restart unless-stopped -p 4416:4416 brainicism/bgutil-ytdlp-pot-provider
   pip install -U bgutil-ytdlp-pot-provider
   ```
3. **Residential proxy**: set `YT_PROXY=http://user:pass@host:port`.

Also make sure **Deno** is installed (`deno --version`) and yt-dlp is up to date:
`pip install -U "yt-dlp[default]"`.

**The assistant joins the voice chat but there's no sound**

- Check that the assistant isn't muted in the voice chat. Tap its name and choose
  *Allow to speak*, or make it an admin with **Manage Video Chats**. The bot posts a
  warning when it detects this.
- Check that `ffmpeg -version` works on the server.
- Keep `AUDIO_QUALITY=high`. Telegram voice chats run at 48 kHz.
- Watch the console. Each track logs `Playing ...` and `Stream ended ... after Ns`.

## 🧱 Project structure

```
MusicBot/
├── __main__.py        # entry point
├── core/
│   ├── clients.py     # bot, assistant and PyTgCalls clients
│   ├── player.py      # voice chat engine: join, stream, queue advance
│   ├── queue.py       # per-chat queue state
│   └── youtube.py     # yt-dlp search and download
├── plugins/           # commands: start/help, play, controls, misc
└── utils/             # buttons, formatters, admin checks
config.py              # environment configuration
generate_session.py    # string session generator
```
