"""
🎬 Telegram Auto Post Bot — Main Entry Point
Handles channel posts via RawUpdateHandler (the only reliable method for bots)
"""

import asyncio
import logging
import os
from aiohttp import web
from pyrogram import Client, filters, idle, raw, types, utils
from pyrogram.types import Message
from pyrogram.handlers import RawUpdateHandler, MessageHandler

from modules.font_setup import ensure_fonts
ensure_fonts()

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

RESOLVED_SOURCE = None
RESOLVED_DEST   = None


# ── Health check server ───────────────────────────────────────────────────────
async def health_check(request):
    return web.Response(text="OK")

async def start_health_server():
    port = int(os.getenv("PORT", 8000))
    web_app = web.Application()
    web_app.router.add_get("/", health_check)
    web_app.router.add_get("/health", health_check)
    runner = web.AppRunner(web_app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logger.info("✅ Health server on port %s", port)


# ── Channel resolver ──────────────────────────────────────────────────────────
async def resolve_channel(client, raw_id, label):
    if isinstance(raw_id, str) and "t.me/" in raw_id:
        raw_id = "@" + raw_id.split("t.me/")[-1].strip("/")
    try:
        chat = await client.get_chat(raw_id)
        logger.info("✅ %s: '%s' (id=%s)", label, chat.title, chat.id)
        return chat
    except Exception as e:
        logger.error("❌ %s failed '%s': %s", label, raw_id, e)
        return None


# ── Core processing logic (shared by raw handler + /test) ────────────────────
async def process_file(client, filename: str, chat_id: int, message_id: int):
    logger.info("🎬 Processing: %s", filename)
    meta = parser.parse(filename)
    logger.info("🔍 title=%s | type=%s | S%sE%s | quality=%s",
                meta["title"], meta["media_type"],
                meta.get("season"), meta.get("episode"), meta.get("quality"))

    cached = await db.get_cached_poster(meta["title"], meta.get("year"), meta["media_type"])
    if cached and cached.get("poster_path") and os.path.exists(cached["poster_path"]):
        poster_path = cached["poster_path"]
        tmdb_data   = cached.get("tmdb_data", {})
        logger.info("✅ Cache hit")
    else:
        logger.info("🌐 Searching TMDB...")
        tmdb_data   = await tmdb.search(meta["title"], meta.get("year"), meta["media_type"])
        logger.info("🎨 Generating poster...")
        poster_path = await poster_gen.create_poster(meta, tmdb_data)
        await db.cache_poster(meta["title"], meta.get("year"), meta["media_type"], poster_path, tmdb_data)

    # Build a minimal fake message object for formatter
    class FakeMsg:
        id = message_id
    caption, keyboard = formatter.build(meta, FakeMsg())

    logger.info("📤 Sending to dest channel...")
    await client.send_photo(
        chat_id=RESOLVED_DEST.id,
        photo=poster_path,
        caption=caption,
        reply_markup=keyboard,
    )
    await client.forward_messages(
        chat_id=RESOLVED_DEST.id,
        from_chat_id=chat_id,
        message_ids=message_id,
    )
    logger.info("✅ Posted: '%s'", meta["title"])


# ── RAW UPDATE HANDLER — catches ALL Telegram updates including channel posts ─
async def on_raw_update(client, update, users, chats):
    try:
        # Only handle new channel messages
        if not isinstance(update, raw.types.UpdateNewChannelMessage):
            return

        msg = update.message
        if not isinstance(msg, raw.types.Message):
            return

        # Get channel id from peer
        peer = msg.peer_id
        if not isinstance(peer, raw.types.PeerChannel):
            return

        channel_id = utils.get_channel_id(peer.channel_id)
        logger.info("📡 Channel post received | channel=%s | msg_id=%s", channel_id, msg.id)

        # Only process from source channel
        if not RESOLVED_SOURCE or channel_id != RESOLVED_SOURCE.id:
            logger.info("   → Ignoring (not source channel, source=%s)",
                        RESOLVED_SOURCE.id if RESOLVED_SOURCE else "None")
            return

        # Extract filename from media
        filename = None
        media = msg.media

        if isinstance(media, raw.types.MessageMediaDocument):
            doc = media.document
            if isinstance(doc, raw.types.Document):
                for attr in doc.attributes:
                    if isinstance(attr, raw.types.DocumentAttributeFilename):
                        filename = attr.file_name
                        break
                    if isinstance(attr, raw.types.DocumentAttributeVideo):
                        # Video file — try to get filename from filename attribute
                        pass

        if not filename:
            # Try caption as filename
            if msg.message and any(msg.message.strip().endswith(ext)
                                   for ext in (".mkv", ".mp4", ".avi", ".ts")):
                filename = msg.message.strip()

        if not filename:
            logger.info("   → No filename found, skipping")
            return

        logger.info("📥 File: %s", filename)
        await process_file(client, filename, channel_id, msg.id)

    except Exception as e:
        logger.exception("❌ Raw update error: %s", e)


# ── /start ────────────────────────────────────────────────────────────────────
@app.on_message(filters.private & filters.command("start"))
async def cmd_start(client, message: Message):
    ok_s = "✅" if RESOLVED_SOURCE else "❌"
    ok_d = "✅" if RESOLVED_DEST   else "❌"
    await message.reply(
        f"🤖 **Bot alive!**\n\n"
        f"{ok_s} Source: `{RESOLVED_SOURCE.title if RESOLVED_SOURCE else 'NOT RESOLVED'}`\n"
        f"{ok_d} Dest:   `{RESOLVED_DEST.title if RESOLVED_DEST else 'NOT RESOLVED'}`\n\n"
        f"/ping — test dest channel\n/test — send test post"
    )


# ── /ping ─────────────────────────────────────────────────────────────────────
@app.on_message(filters.private & filters.command("ping"))
async def cmd_ping(client, message: Message):
    if not RESOLVED_DEST:
        await message.reply("❌ Dest not resolved.")
        return
    try:
        await client.send_message(RESOLVED_DEST.id, "🏓 Ping — dest works!")
        await message.reply("✅ Ping sent to dest channel!")
    except Exception as e:
        await message.reply(f"❌ `{e}`")


# ── /test — full pipeline test without needing to upload ─────────────────────
@app.on_message(filters.private & filters.command("test"))
async def cmd_test(client, message: Message):
    if not RESOLVED_DEST:
        await message.reply("❌ Dest not resolved.")
        return
    await message.reply("⏳ Running test...")
    try:
        meta        = parser.parse("Beast.Games.S02E06.720p.WEB-DL.mkv")
        tmdb_data   = await tmdb.search(meta["title"], meta.get("year"), meta["media_type"])
        poster_path = await poster_gen.create_poster(meta, tmdb_data)

        class FakeMsg:
            id = 0
        caption, keyboard = formatter.build(meta, FakeMsg())

        await client.send_photo(
            chat_id=RESOLVED_DEST.id,
            photo=poster_path,
            caption=f"🧪 TEST POST\n\n{caption}",
            reply_markup=keyboard,
        )
        await message.reply("✅ Test post sent to dest channel!")
    except Exception as e:
        logger.exception("Test failed")
        await message.reply(f"❌ Test failed:\n`{e}`")


# ── Start ─────────────────────────────────────────────────────────────────────
async def main():
    global RESOLVED_SOURCE, RESOLVED_DEST

    await start_health_server()
    await db.connect()
    logger.info("🚀 Bot starting…")

    # Register raw handler BEFORE starting the client
    app.add_handler(RawUpdateHandler(on_raw_update))

    async with app:
        me = await app.get_me()
        logger.info("🤖 Bot: @%s (id=%s)", me.username, me.id)

        RESOLVED_SOURCE = await resolve_channel(app, Config.SOURCE_CHANNEL_ID, "SOURCE")
        RESOLVED_DEST   = await resolve_channel(app, Config.DEST_CHANNEL_ID,   "DEST")

        if RESOLVED_SOURCE and RESOLVED_DEST:
            logger.info("✅ Both channels ready! Upload a file to source channel now.")
        else:
            logger.error("❌ Channel resolution failed!")

        await idle()


if __name__ == "__main__":
    from pyrogram.errors import FloodWait
    import time
    while True:
        try:
            asyncio.run(main())
            break
        except FloodWait as e:
            logger.warning("⏳ FloodWait %s sec...", e.value)
            time.sleep(e.value + 5)
        except KeyboardInterrupt:
            break
