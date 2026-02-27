"""
modules/database.py
────────────────────
MongoDB async wrapper using motor.
Collections:
  • poster_cache   — TMDB results keyed by (title, year, media_type)
  • manual_posters — admin-supplied Telegram file_ids
  • posted_files   — deduplication log
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient

from modules.config import Config

logger = logging.getLogger("Database")


class Database:

    def __init__(self, mongo_uri: str):
        self._uri     = mongo_uri
        self._client  = None
        self._db      = None

    async def connect(self):
        self._client = AsyncIOMotorClient(self._uri)
        self._db     = self._client[Config.MONGO_DB_NAME]
        # Indexes
        await self._db.poster_cache.create_index(
            [("title", 1), ("year", 1), ("media_type", 1)], unique=True
        )
        await self._db.posted_files.create_index("message_id", unique=True)
        logger.info("✅ Connected to MongoDB: %s", Config.MONGO_DB_NAME)

    # ── Poster cache ──────────────────────────────────────────────────────────

    async def get_cached_poster(
        self, title: str, year: Optional[int], media_type: str
    ) -> Optional[dict]:
        doc = await self._db.poster_cache.find_one(
            {"title": title.lower(), "year": year, "media_type": media_type}
        )
        return doc

    async def cache_poster(
        self,
        title: str,
        year: Optional[int],
        media_type: str,
        poster_path: str,
        tmdb_data: dict,
    ):
        await self._db.poster_cache.update_one(
            {"title": title.lower(), "year": year, "media_type": media_type},
            {
                "$set": {
                    "poster_path": poster_path,
                    "tmdb_data":   tmdb_data,
                    "updated_at":  datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

    # ── Manual poster ─────────────────────────────────────────────────────────

    async def save_manual_poster(self, hint: str, file_id: str):
        await self._db.manual_posters.update_one(
            {"hint": hint.lower()},
            {"$set": {"file_id": file_id, "saved_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

    async def get_manual_poster(self, hint: str) -> Optional[dict]:
        return await self._db.manual_posters.find_one({"hint": hint.lower()})

    # ── Deduplication ─────────────────────────────────────────────────────────

    async def is_posted(self, message_id: int) -> bool:
        doc = await self._db.posted_files.find_one({"message_id": message_id})
        return doc is not None

    async def mark_posted(self, message_id: int, title: str):
        await self._db.posted_files.insert_one(
            {
                "message_id": message_id,
                "title":      title,
                "posted_at":  datetime.now(timezone.utc),
            }
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def close(self):
        if self._client:
            self._client.close()
            logger.info("MongoDB connection closed.")
