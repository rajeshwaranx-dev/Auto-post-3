"""
modules/tmdb_client.py
──────────────────────
Async TMDB API wrapper — search + poster download.
"""

import asyncio
import logging
import os
from typing import Optional

import aiohttp
import aiofiles

from modules.config import Config

logger = logging.getLogger("TMDBClient")


class TMDBClient:
    """Async TMDB API client with poster downloading."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base    = Config.TMDB_BASE_URL
        self.img_base = Config.TMDB_IMAGE_BASE
        self._session: Optional[aiohttp.ClientSession] = None

    # ── Session management ────────────────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"User-Agent": "AutoPostBot/1.0"},
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # ── Public API ────────────────────────────────────────────────────────────

    async def search(self, title: str, year: Optional[int], media_type: str) -> dict:
        """
        Search TMDB and return a metadata dict that includes:
          tmdb_id, title, overview, release_year, poster_url,
          local_poster_path (downloaded), vote_average
        Returns {} if nothing is found.
        """
        endpoint = "tv" if media_type == "series" else "movie"
        params = {
            "api_key": self.api_key,
            "query":   title,
            "language": "en-US",
            "page":    1,
        }
        if year:
            params["year" if media_type == "movie" else "first_air_date_year"] = year

        session = await self._get_session()

        try:
            async with session.get(f"{self.base}/search/{endpoint}", params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except Exception as exc:
            logger.error("TMDB search failed for '%s': %s", title, exc)
            return {}

        results = data.get("results", [])
        if not results:
            logger.warning("No TMDB results for '%s' (%s)", title, media_type)
            return {}

        best = self._pick_best(results, title, year, media_type)
        return await self._enrich(best, media_type)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _pick_best(self, results: list, title: str, year: Optional[int], media_type: str) -> dict:
        """Score candidates — prefer exact title + year match."""
        title_lc = title.lower()

        def score(item: dict) -> float:
            candidate = (item.get("title") or item.get("name") or "").lower()
            s = 0.0
            if candidate == title_lc:
                s += 10
            elif title_lc in candidate or candidate in title_lc:
                s += 5
            if year:
                release = item.get("release_date") or item.get("first_air_date") or ""
                if release.startswith(str(year)):
                    s += 3
            s += (item.get("popularity") or 0) / 1000
            return s

        return max(results, key=score)

    async def _enrich(self, item: dict, media_type: str) -> dict:
        """Download poster and build enriched dict."""
        poster_path_remote = item.get("poster_path")
        local_poster = None

        if poster_path_remote:
            poster_url  = f"{self.img_base}{poster_path_remote}"
            local_poster = await self._download_poster(poster_url, item.get("id", 0))

        release_date = item.get("release_date") or item.get("first_air_date") or ""
        return {
            "tmdb_id":          item.get("id"),
            "title":            item.get("title") or item.get("name") or "",
            "overview":         item.get("overview", ""),
            "release_year":     int(release_date[:4]) if release_date else None,
            "poster_url":       f"{self.img_base}{poster_path_remote}" if poster_path_remote else None,
            "local_poster_path": local_poster,
            "vote_average":     round(item.get("vote_average", 0), 1),
            "media_type":       media_type,
        }

    async def _download_poster(self, url: str, tmdb_id: int) -> Optional[str]:
        """Download poster to local cache dir; return path."""
        os.makedirs(Config.POSTER_OUTPUT_DIR, exist_ok=True)
        dest = os.path.join(Config.POSTER_OUTPUT_DIR, f"raw_{tmdb_id}.jpg")

        if os.path.exists(dest):
            return dest  # Already cached on disk

        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                resp.raise_for_status()
                async with aiofiles.open(dest, "wb") as f:
                    async for chunk in resp.content.iter_chunked(65536):
                        await f.write(chunk)
            logger.info("Downloaded poster: %s", dest)
            return dest
        except Exception as exc:
            logger.error("Failed to download poster %s: %s", url, exc)
            return None
