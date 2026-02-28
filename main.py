"""
🎬 Telegram Auto Post Bot — Main Entry Point
"""

import asyncio
import logging
import os
from aiohttp import web
from pyrogram import Client, filters, idle, raw
from pyrogram.types import Message
from pyrogram.handlers import RawUpdateHandler

from modules.font_setup import ensure_fonts
ensure_fonts()  # Download fonts before anything else

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


# ── Health check web server (keeps Koyeb/Heroku happy) ───────────────────────
async def health_check(request):
    return web.Response(text="OK")

async def start_health_server():
    port = int(os.getenv("PORT", 8000))
    web_app = web.Application()
    web_app.router.add_get("/", health_check)
    web_app.router.add_get("/health", health_check)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("✅ Health server running on port %s", port)


# ── Channel resolver ──────────────────────────────────────────────────────────
async def resolve_channel(client, raw_id, label):
    if isinstance(raw_id, str) and "t.me/" in raw_id:
        raw_id = "@" + raw_id.split("t.me/")[-1].strip("/")
    try:
        chat = await client.get_chat(raw_id)
        logger.info("✅ %s resolved: '%s' (id=%s)", label, chat.title, chat.id)
        return chat
    except Exception as e:
        logger.error("❌ %s failed '%s': %s", label, raw_id, e)
        return None


# ── Raw update debugger ───────────────────────────────────────────────────────
async def raw_update_handler(client, update, users, chats):
    update_type = type(update).__name__
    if "Channel" in update_type or "Message" in update_type:
        logger.info("📡 RAW: %s", update_type)


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
        await message.reply("✅ Ping sent!")
    except Exception as e:
        await message.reply(f"❌ `{e}`")


# ── /test ─────────────────────────────────────────────────────────────────────
@app.on_message(filters.private & filters.command("test"))
async def cmd_test(client, message: Message):
    if not RESOLVED_DEST:
        await message.reply("❌ Dest not resolved.")
        return
    try:
        meta        = parser.parse("Beast.Games.S02E06.720p.WEB-DL.mkv")
        tmdb_data   = await tmdb.search(meta["title"], meta.get("year"), meta["media_type"])
        poster_path = await poster_gen.create_poster(meta, tmdb_data)
        caption, keyboard = formatter.build(meta, message)
        await client.send_photo(
            chat_id=RESOLVED_DEST.id,
            photo=poster_path,
            caption=f"🧪 TEST\n\n{caption}",
            reply_markup=keyboard,
        )
        await message.reply("✅ Test post sent!")
    except Exception as e:
        logger.exception("Test failed")
        await message.reply(f"❌ `{e}`")


# ── Main file handler ─────────────────────────────────────────────────────────
@app.on_message(filters.document | filters.video | filters.audio)
async def handle_new_file(client, message: Message):
    if not RESOLVED_SOURCE or message.chat.id != RESOLVED_SOURCE.id:
        return
    logger.info("📥 FILE | id=%s | doc=%s | video=%s",
                message.id, bool(message.document), bool(message.video))
    try:
        filename = _extract_filename(message)
        if not filename:
            logger.warning("⚠️  No filename in msg %s", message.id)
            return

        logger.info("🎬 Processing: %s", filename)
        meta = parser.parse(filename)

        cached = await db.get_cached_poster(meta["title"], meta.get("year"), meta["media_type"])
        if cached and cached.get("poster_path") and os.path.exists(cached["poster_path"]):
            poster_path = cached["poster_path"]
            tmdb_data   = cached.get("tmdb_data", {})
        else:
            tmdb_data   = await tmdb.search(meta["title"], meta.get("year"), meta["media_type"])
            poster_path = await poster_gen.create_poster(meta, tmdb_data)
            await db.cache_poster(meta["title"], meta.get("year"), meta["media_type"], poster_path, tmdb_data)

        caption, keyboard = formatter.build(meta, message)
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
        logger.info("✅ Posted '%s'", meta["title"])

    except Exception as exc:
        logger.exception("❌ Error on msg %s: %s", message.id, exc)


@app.on_message(filters.photo)
async def handle_manual_poster(client, message: Message):
    if not RESOLVED_SOURCE or message.chat.id != RESOLVED_SOURCE.id:
        return
    if not message.caption:
        return
    await db.save_manual_poster(message.caption.strip(), message.photo.file_id)
    logger.info("📌 Manual poster: %s", message.caption.strip())


# ── Helpers ───────────────────────────────────────────────────────────────────
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


# ── Start ─────────────────────────────────────────────────────────────────────
async def main():
    global RESOLVED_SOURCE, RESOLVED_DEST

    # Start health check server FIRST so Koyeb doesn't kill us
    await start_health_server()

    await db.connect()
    logger.info("🚀 Bot starting…")

    app.add_handler(RawUpdateHandler(raw_update_handler))

    async with app:
        me = await app.get_me()
        logger.info("🤖 Bot: @%s (id=%s)", me.username, me.id)

        RESOLVED_SOURCE = await resolve_channel(app, Config.SOURCE_CHANNEL_ID, "SOURCE")
        RESOLVED_DEST   = await resolve_channel(app, Config.DEST_CHANNEL_ID,   "DEST")

        if RESOLVED_SOURCE and RESOLVED_DEST:
            logger.info("✅ Both channels resolved!")
        else:
            logger.error("❌ Channel resolution failed!")

        logger.info("💡 DM @%s with /start /ping /test", me.username)
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
