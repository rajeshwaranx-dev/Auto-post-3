"""
modules/config.py — Environment-based configuration
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── Telegram ──────────────────────────────────────────────────────────────
    BOT_TOKEN: str        = os.environ["BOT_TOKEN"]
    API_ID: int           = int(os.environ["API_ID"])
    API_HASH: str         = os.environ["API_HASH"]

    # Channel IDs (use -100xxxxxxxxxx format for public channels)
    SOURCE_CHANNEL_ID: int = int(os.environ["SOURCE_CHANNEL_ID"])
    DEST_CHANNEL_ID: int   = int(os.environ["DEST_CHANNEL_ID"])

    # ── TMDB ──────────────────────────────────────────────────────────────────
    TMDB_API_KEY: str     = os.environ["TMDB_API_KEY"]
    TMDB_BASE_URL: str    = "https://api.themoviedb.org/3"
    TMDB_IMAGE_BASE: str  = "https://image.tmdb.org/t/p/original"

    # ── MongoDB ───────────────────────────────────────────────────────────────
    MONGO_URI: str        = os.environ["MONGO_URI"]
    MONGO_DB_NAME: str    = os.getenv("MONGO_DB_NAME", "autopostbot")

    # ── Poster Settings ───────────────────────────────────────────────────────
    POSTER_WIDTH: int     = 1080
    POSTER_MIN_HEIGHT: int = 1600
    POSTER_OUTPUT_DIR: str = os.getenv("POSTER_OUTPUT_DIR", "posters")

    # ── Fallback ──────────────────────────────────────────────────────────────
    FALLBACK_POSTER: str  = "assets/fallback.jpg"
    FONT_BOLD: str        = "assets/fonts/bold.ttf"
    FONT_REGULAR: str     = "assets/fonts/regular.ttf"
