import logging
import sys

import config

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
for noisy in ("pyrogram", "pytgcalls", "ntgcalls"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

LOGGER = logging.getLogger("MusicBot")

_missing = [
    name
    for name in ("API_ID", "API_HASH", "BOT_TOKEN", "STRING_SESSION")
    if not getattr(config, name)
]
if _missing:
    LOGGER.error("Missing required config: %s (see .env.example)", ", ".join(_missing))
    sys.exit(1)
