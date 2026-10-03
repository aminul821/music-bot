"""Generate a Pyrogram string session for the assistant account.

Run: python generate_session.py
Log in with the account (not the bot) that should join voice chats, then put the
printed string into STRING_SESSION. Keep it secret: it grants full account access.
"""
import asyncio

from pyrogram import Client


async def main() -> None:
    api_id = int(input("API_ID: ").strip())
    api_hash = input("API_HASH: ").strip()
    async with Client("session_gen", api_id=api_id, api_hash=api_hash, in_memory=True) as app:
        session = await app.export_session_string()
        await app.send_message(
            "me",
            f"<b>Your STRING_SESSION</b> (keep it secret!):\n\n<code>{session}</code>",
        )
        print("\nSTRING_SESSION:\n")
        print(session)
        print("\nAlso saved to your Saved Messages.")


if __name__ == "__main__":
    asyncio.run(main())
