from pyrogram import Client
from pytgcalls import PyTgCalls

import config

bot = Client(
    "MusicBot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    in_memory=True,
    plugins=dict(root="MusicBot.plugins"),
    # Each /play may wait on a download; enough workers keeps other commands instant.
    workers=32,
)

assistant = Client(
    "MusicAssistant",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    session_string=config.STRING_SESSION,
    in_memory=True,
    no_updates=False,
)

call = PyTgCalls(assistant)
