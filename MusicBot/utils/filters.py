from pyrogram import filters

PREFIXES = ["/", "!", "."]


def command(*names: str):
    return filters.command(list(names), prefixes=PREFIXES)
