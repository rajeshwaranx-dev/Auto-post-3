"""
🎬 Telegram Auto Post Bot — Main Entry Point
Production-ready | Pyrogram + MongoDB + TMDB
"""

import asyncio
import logging
import os
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pyrogram.errors import ChatAdminRequired, ChannelPrivate, PeerIdInvalid

from modules.config import Config
from modules.database import Database
from modules.filename_parser import FilenameParser
from modules.tmdb_client import TMDBClient
from modules.poster_generator import PosterGenerator
from modules.post_formatter import PostFormatter

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("AutoPostBot")

# ─── App ─────────────────────────────────────────────────────────────────────
app = Client(
    "auto_post_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
)

# ─── Singletons ──────────────────────────────────────────────────────────────
db = Database(Config.MONGO_URI)
tmdb = TMDBClient(Config.TMDB_API_KEY)
poster_gen = PosterGenerator()
formatter = PostFormatter()
parser = FilenameParser()


# ─── /start — DM the bot to confirm it's alive ───────────────────────────────
@app.on_message(filters.private & filters.command("start"))
async def cmd_start(client: Client, message: Message):
    await message.reply(
        "✅ **Bot is alive!**\n\n"
        f"📡 Source channel: `{Config.SOURCE_CHANNEL_ID}`\n"
        f"📺 Dest channel: `{Config.DEST_CHANNEL_ID}`\n\n"
        "Use /check to verify channel admin status."
    )


# ─── /check — verifies bot can see both channels ─────────────────────────────
@app.on_message(filters.private & filters.command("check"))
async def cmd_check(client: Client, message: Message):
    results = []

    for label, cid in [("SOURCE", Config.SOURCE_CHANNEL_ID),
                       ("DEST",   Config.DEST_CHANNEL_ID)]:
        try:
            chat = await client.get_chat(cid)
            # Try to get bot's own member info to check admin status
            member = await client.get_chat_member(cid, "me")
            status = member.status.value  # "administrator", "member", etc.
            results.append(f"✅ {label}: **{chat.title}** — bot status: `{status}`")
        except PeerIdInvalid:
            results.append(f"❌ {label} `{cid}`: Invalid channel ID — check your .env")
        except ChannelPrivate:
            results.append(f"❌ {label} `{cid}`: Bot is NOT a member — add bot as admin first")
        except Exception as e:
            results.append(f"⚠️ {label} `{cid}`: {e}")

    await message.reply("\n".join(results))


# ─── /ping — upload a test file to source channel then run /ping ─────────────
@app.on_message(filters.private & filters.command("ping"))
async def cmd_ping(client: Client, message: Message):
    """Force-send a test message to dest channel to verify dest posting works."""
    try:
        await client.send_message(Config.DEST_CHANNEL_ID, "🏓 Ping from AutoPostBot — dest channel is working!")
        await message.reply("✅ Sent ping to dest channel successfully!")
    except Exception as e:
        await message.reply(f"❌ Failed to post to dest channel:\n`{e}`")


# ─── Main file handler ────────────────────────────────────────────────────────
# NOTE: Pyrogram bots receive channel posts ONLY when bot is ADMIN of the channel
@app.on_message(
    filters.chat(Config.SOURCE_CHANNEL_ID)
    & (filters.video | filters.document | filters.audio)
)
async def handle_new_file(client: Client, message: Message):
    try:
        logger.info("📥 FILE received | id=%s | doc=%s | video=%s",
                    message.id, bool(message.document), bool(message.video))

        filename = _extract_filename(message)
        if not filename:
            logger.warning("⚠️  No filename in message %s — skipping.", message.id)
            return

        logger.info("🎬 Processing: %s", filename)

        meta = parser.parse(filename)
        logger.info("🔍 title=%s | type=%s | S%sE%s | quality=%s",
                    meta["title"], meta["media_type"],
                    meta.get("season"), meta.get("episode"), meta.get("quality"))

        cached = await db.get_cached_poster(meta["title"], meta.get("year"), meta["media_type"])
        if cached and cached.get("poster_path") and os.path.exists(cached["poster_path"]):
            logger.info("✅ Cache hit for '%s'", meta["title"])
            poster_path = cached["poster_path"]
            tmdb_data   = cached.get("tmdb_data", {})
        else:
            logger.info("🌐 TMDB searching '%s'...", meta["title"])
            tmdb_data   = await tmdb.search(meta["title"], meta.get("year"), meta["media_type"])
            logger.info("🎨 Generating poster...")
            poster_path = await poster_gen.create_poster(meta, tmdb_data)
            await db.cache_poster(meta["title"], meta.get("year"), meta["media_type"], poster_path, tmdb_data)

        caption, keyboard = formatter.build(meta, message)

        logger.info("📤 Posting to dest channel %s...", Config.DEST_CHANNEL_ID)
        await client.send_photo(
            chat_id=Config.DEST_CHANNEL_ID,
            photo=poster_path,
            caption=caption,
            reply_markup=keyboard,
        )
        await client.forward_messages(
            chat_id=Config.DEST_CHANNEL_ID,
            from_chat_id=message.chat.id,
            message_ids=message.id,
        )
        logger.info("✅ Posted '%s' successfully.", meta["title"])

    except Exception as exc:
        logger.exception("❌ Error on message %s: %s", message.id, exc)


@app.on_message(filters.chat(Config.SOURCE_CHANNEL_ID) & filters.photo)
async def handle_manual_poster(client: Client, message: Message):
    if not message.caption:
        return
    await db.save_manual_poster(message.caption.strip(), message.photo.file_id)
    logger.info("📌 Manual poster saved for: %s", message.caption.strip())


# ─── DEBUG: log EVERY message received anywhere ───────────────────────────────
# This tells us if the bot receives anything at all from the source channel
@app.on_message(filters.chat(Config.SOURCE_CHANNEL_ID))
async def debug_source(client: Client, message: Message):
    logger.info(
        "🔔 SOURCE MSG | id=%s | text=%s | doc=%s | video=%s | photo=%s | service=%s",
        message.id, bool(message.text), bool(message.document),
        bool(message.video), bool(message.photo), bool(message.service)
    )


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


# ─── Startup channel self-check ───────────────────────────────────────────────
async def verify_channels(client: Client):
    logger.info("🔍 Verifying channel access...")
    all_ok = True

    for label, cid in [("SOURCE", Config.SOURCE_CHANNEL_ID),
                       ("DEST",   Config.DEST_CHANNEL_ID)]:
        try:
            chat   = await client.get_chat(cid)
            member = await client.get_chat_member(cid, "me")
            status = member.status.value
            is_admin = status == "administrator"
            icon = "✅" if is_admin else "⚠️ "
            logger.info("%s %s channel: '%s' | bot status: %s %s",
                        icon, label, chat.title, status,
                        "← NEEDS ADMIN RIGHTS" if not is_admin else "")
            if not is_admin:
                all_ok = False
        except PeerIdInvalid:
            logger.error("❌ %s channel ID %s is INVALID — fix SOURCE_CHANNEL_ID in .env", label, cid)
            all_ok = False
        except ChannelPrivate:
            logger.error("❌ Bot is NOT a member of %s channel %s — add bot as admin!", label, cid)
            all_ok = False
        except Exception as e:
            logger.error("❌ %s channel %s error: %s", label, cid, e)
            all_ok = False

    if all_ok:
        logger.info("✅ Both channels verified — bot has admin rights!")
    else:
        logger.error("⚠️  FIX CHANNEL ISSUES ABOVE or the bot will not work.")

    return all_ok


# ─── Start ───────────────────────────────────────────────────────────────────
async def main():
    await db.connect()
    logger.info("🚀 Bot starting…")
    logger.info("📡 Source channel ID: %s", Config.SOURCE_CHANNEL_ID)
    logger.info("📺 Dest   channel ID: %s", Config.DEST_CHANNEL_ID)

    async with app:
        me = await app.get_me()
        logger.info("🤖 Bot: @%s (id=%s)", me.username, me.id)

        await verify_channels(app)

        logger.info("✅ Bot is LIVE — waiting for files…")
        logger.info("💡 DM @%s with /check to verify admin status anytime", me.username)
        await idle()


if __name__ == "__main__":
    asyncio.run(main())
