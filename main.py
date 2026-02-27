"""
🎬 Telegram Auto Post Bot — Main Entry Point
"""

import asyncio
import logging
import os
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pyrogram.errors import ChatAdminRequired, ChannelPrivate, PeerIdInvalid, UsernameNotOccupied

from modules.config import Config
from modules.database import Database
from modules.filename_parser import FilenameParser
from modules.tmdb_client import TMDBClient
from modules.poster_generator import PosterGenerator
from modules.post_formatter import PostFormatter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("AutoPostBot")

app = Client(
    "auto_post_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
)

db = Database(Config.MONGO_URI)
tmdb = TMDBClient(Config.TMDB_API_KEY)
poster_gen = PosterGenerator()
formatter = PostFormatter()
parser = FilenameParser()

# Will be populated at startup after peer resolution
RESOLVED_SOURCE = None
RESOLVED_DEST   = None


async def resolve_channel(client: Client, raw_id, label: str):
    """
    Resolve a channel to a usable peer.
    Accepts: numeric ID (-100xxx), @username, or t.me/username link.
    Returns the resolved chat object or None.
    """
    # Normalise t.me links → @username
    if isinstance(raw_id, str) and "t.me/" in raw_id:
        raw_id = "@" + raw_id.split("t.me/")[-1].strip("/")

    try:
        chat = await client.get_chat(raw_id)
        logger.info("✅ %s resolved: '%s' (id=%s)", label, chat.title, chat.id)
        return chat
    except Exception as e:
        logger.error("❌ %s could not be resolved with value '%s': %s", label, raw_id, e)
        logger.error(
            "   → If this is a private channel, make sure the bot is ADMIN.\n"
            "   → Try using the @username instead of numeric ID in your .env"
        )
        return None


# ─── /start ──────────────────────────────────────────────────────────────────
@app.on_message(filters.private & filters.command("start"))
async def cmd_start(client: Client, message: Message):
    src  = f"`{Config.SOURCE_CHANNEL_ID}`"
    dest = f"`{Config.DEST_CHANNEL_ID}`"
    ok_s = "✅" if RESOLVED_SOURCE else "❌"
    ok_d = "✅" if RESOLVED_DEST   else "❌"
    await message.reply(
        f"🤖 **AutoPostBot is alive!**\n\n"
        f"{ok_s} Source: {src} → `{RESOLVED_SOURCE.title if RESOLVED_SOURCE else 'NOT RESOLVED'}`\n"
        f"{ok_d} Dest:   {dest} → `{RESOLVED_DEST.title if RESOLVED_DEST else 'NOT RESOLVED'}`\n\n"
        f"Use /ping to test posting to dest channel."
    )


# ─── /ping ───────────────────────────────────────────────────────────────────
@app.on_message(filters.private & filters.command("ping"))
async def cmd_ping(client: Client, message: Message):
    if not RESOLVED_DEST:
        await message.reply("❌ Dest channel is not resolved. Check your DEST_CHANNEL_ID.")
        return
    try:
        await client.send_message(RESOLVED_DEST.id, "🏓 Ping — dest channel works!")
        await message.reply("✅ Ping sent to dest channel!")
    except Exception as e:
        await message.reply(f"❌ Failed:\n`{e}`")


# ─── Main file handler ────────────────────────────────────────────────────────
@app.on_message(filters.document | filters.video | filters.audio)
async def handle_new_file(client: Client, message: Message):
    # Only process messages from the source channel
    if not RESOLVED_SOURCE:
        return
    if message.chat.id != RESOLVED_SOURCE.id:
        return

    try:
        logger.info("📥 FILE | id=%s | doc=%s | video=%s",
                    message.id, bool(message.document), bool(message.video))

        filename = _extract_filename(message)
        if not filename:
            logger.warning("⚠️  No filename in message %s", message.id)
            return

        logger.info("🎬 Processing: %s", filename)
        meta = parser.parse(filename)
        logger.info("🔍 title=%s | type=%s | S%sE%s | quality=%s",
                    meta["title"], meta["media_type"],
                    meta.get("season"), meta.get("episode"), meta.get("quality"))

        # Poster
        cached = await db.get_cached_poster(meta["title"], meta.get("year"), meta["media_type"])
        if cached and cached.get("poster_path") and os.path.exists(cached["poster_path"]):
            logger.info("✅ Cache hit for '%s'", meta["title"])
            poster_path = cached["poster_path"]
            tmdb_data   = cached.get("tmdb_data", {})
        else:
            tmdb_data   = await tmdb.search(meta["title"], meta.get("year"), meta["media_type"])
            poster_path = await poster_gen.create_poster(meta, tmdb_data)
            await db.cache_poster(meta["title"], meta.get("year"), meta["media_type"], poster_path, tmdb_data)

        caption, keyboard = formatter.build(meta, message)

        logger.info("📤 Posting to dest (id=%s)...", RESOLVED_DEST.id)
        await client.send_photo(
            chat_id=RESOLVED_DEST.id,
            photo=poster_path,
            caption=caption,
            reply_markup=keyboard,
        )
        await client.forward_messages(
            chat_id=RESOLVED_DEST.id,
            from_chat_id=RESOLVED_SOURCE.id,
            message_ids=message.id,
        )
        logger.info("✅ Posted '%s' successfully.", meta["title"])

    except Exception as exc:
        logger.exception("❌ Error on message %s: %s", message.id, exc)


@app.on_message(filters.photo)
async def handle_manual_poster(client: Client, message: Message):
    if not RESOLVED_SOURCE or message.chat.id != RESOLVED_SOURCE.id:
        return
    if not message.caption:
        return
    await db.save_manual_poster(message.caption.strip(), message.photo.file_id)
    logger.info("📌 Manual poster saved: %s", message.caption.strip())


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _extract_filename(message: Message) -> str | None:
    if message.document and message.document.file_name:
        return message.document.file_name
    if message.video and message.video.file_name:
        return message.video.file_name
    if message.caption:
        cap = message.caption.strip()
        if any(cap.endswith(ext) for ext in (".mkv", ".mp4", ".avi", ".ts", ".m2ts")):
            return cap
    return None


# ─── Start ───────────────────────────────────────────────────────────────────
async def main():
    global RESOLVED_SOURCE, RESOLVED_DEST

    await db.connect()
    logger.info("🚀 Bot starting…")

    async with app:
        me = await app.get_me()
        logger.info("🤖 Bot: @%s (id=%s)", me.username, me.id)

        # Resolve both channels
        logger.info("🔍 Resolving channels...")
        logger.info("   SOURCE = %s", Config.SOURCE_CHANNEL_ID)
        logger.info("   DEST   = %s", Config.DEST_CHANNEL_ID)

        RESOLVED_SOURCE = await resolve_channel(app, Config.SOURCE_CHANNEL_ID, "SOURCE")
        RESOLVED_DEST   = await resolve_channel(app, Config.DEST_CHANNEL_ID,   "DEST")

        if not RESOLVED_SOURCE or not RESOLVED_DEST:
            logger.error("━" * 60)
            logger.error("CHANNEL RESOLUTION FAILED. Try using @username instead")
            logger.error("of numeric ID for the failing channel in your .env:")
            logger.error("  DEST_CHANNEL_ID=@your_channel_username")
            logger.error("━" * 60)
        else:
            logger.info("✅ Both channels resolved — bot is ready!")

        logger.info("💡 DM @%s with /start or /ping to test", me.username)
        await idle()


if __name__ == "__main__":
    asyncio.run(main())
    
