"""
modules/poster_generator.py
────────────────────────────
Generates premium-styled movie/series posters using Pillow (PIL).

Design language:
  • Full HD width (1080 px)
  • Dark gradient overlay at bottom 40 %
  • Bold, centered Netflix-style title
  • Season / Episode tag for series
  • Subtle drop-shadow on text
"""

import logging
import os
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from modules.config import Config

logger = logging.getLogger("PosterGenerator")


# ── Constants ─────────────────────────────────────────────────────────────────

TARGET_W   = Config.POSTER_WIDTH           # 1080
MIN_H      = Config.POSTER_MIN_HEIGHT      # 1600
GRAD_START = 0.55                          # gradient begins at 55 % from top
OUT_DIR    = Config.POSTER_OUTPUT_DIR

# Gradient colours  (RGBA)
GRAD_TOP_RGBA   = (0, 0, 0, 0)            # transparent
GRAD_BOT_RGBA   = (0, 0, 0, 230)          # near-black

# Text colours
TITLE_COLOR     = (255, 255, 255, 255)
SUBTITLE_COLOR  = (200, 200, 200, 230)
RATING_COLOR    = (255, 215, 0,   220)    # gold

# Font sizes (scaled to 1080 px canvas)
TITLE_FONT_MAX   = 80
TITLE_FONT_MIN   = 40
SUB_FONT_SIZE    = 48
META_FONT_SIZE   = 36
SHADOW_OFFSET    = 3


class PosterGenerator:

    def __init__(self):
        os.makedirs(OUT_DIR, exist_ok=True)
        self._font_bold    = self._load_font(Config.FONT_BOLD,    TITLE_FONT_MAX)
        self._font_regular = self._load_font(Config.FONT_REGULAR, SUB_FONT_SIZE)
        self._font_meta    = self._load_font(Config.FONT_REGULAR, META_FONT_SIZE)

    # ── Public API ────────────────────────────────────────────────────────────

    async def create_poster(self, meta: dict, tmdb_data: dict) -> str:
        """
        Return path to the finished poster image.
        Uses TMDB poster if available, else fallback template.
        """
        local_raw = (tmdb_data or {}).get("local_poster_path")
        try:
            if local_raw and os.path.exists(local_raw):
                canvas = self._open_and_resize(local_raw)
            else:
                canvas = self._make_fallback_canvas(meta)

            canvas = self._apply_gradient(canvas)
            canvas = self._draw_text_overlay(canvas, meta, tmdb_data or {})

            out_path = self._output_path(meta)
            canvas.convert("RGB").save(out_path, "JPEG", quality=92)
            logger.info("Poster saved: %s", out_path)
            return out_path

        except Exception as exc:
            logger.exception("Poster generation failed: %s", exc)
            return Config.FALLBACK_POSTER

    # ── Image prep ────────────────────────────────────────────────────────────

    def _open_and_resize(self, path: str) -> Image.Image:
        img = Image.open(path).convert("RGBA")
        # Scale to TARGET_W preserving aspect; ensure minimum height
        w, h = img.size
        new_h = max(int(h * TARGET_W / w), MIN_H)
        return img.resize((TARGET_W, new_h), Image.LANCZOS)

    def _make_fallback_canvas(self, meta: dict) -> Image.Image:
        """Gradient fallback poster."""
        img = Image.new("RGBA", (TARGET_W, MIN_H), (20, 20, 30, 255))
        draw = ImageDraw.Draw(img)

        # Draw diagonal pattern
        for i in range(0, TARGET_W + MIN_H, 80):
            draw.line([(0, i), (i, 0)], fill=(35, 35, 50, 255), width=1)

        # Central icon placeholder
        cx, cy = TARGET_W // 2, MIN_H // 2
        draw.ellipse(
            [cx - 120, cy - 120, cx + 120, cy + 120],
            fill=(40, 40, 60, 255),
            outline=(80, 80, 120, 200),
            width=3,
        )
        # Film strip symbol
        for dy in [-40, 0, 40]:
            draw.rectangle([cx - 60, cy + dy - 15, cx + 60, cy + dy + 15],
                           fill=(60, 60, 90, 255))

        return img

    # ── Gradient overlay ──────────────────────────────────────────────────────

    def _apply_gradient(self, img: Image.Image) -> Image.Image:
        w, h = img.size
        grad_start_y = int(h * GRAD_START)
        grad_h = h - grad_start_y

        gradient = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(gradient)

        for y in range(grad_h):
            alpha = int(GRAD_BOT_RGBA[3] * (y / grad_h) ** 1.5)
            draw.line([(0, grad_start_y + y), (w, grad_start_y + y)],
                      fill=(0, 0, 0, alpha))

        return Image.alpha_composite(img, gradient)

    # ── Text overlay ──────────────────────────────────────────────────────────

    def _draw_text_overlay(self, img: Image.Image, meta: dict, tmdb: dict) -> Image.Image:
        draw  = ImageDraw.Draw(img)
        w, h  = img.size
        title = meta["title"]
        is_series = meta["media_type"] == "series"

        # Padding
        pad   = 40
        bottom = h - 60

        # ── Meta line (year / quality / rating) ───────────────────────────────
        rating  = tmdb.get("vote_average", "")
        year    = meta.get("year") or (tmdb.get("release_year") or "")
        quality = meta.get("display_quality") or meta.get("quality", "")
        meta_parts = [str(p) for p in [year, quality, (f"★ {rating}" if rating else "")] if p]
        meta_line  = "  •  ".join(meta_parts)

        y_cursor = bottom
        if meta_line:
            y_cursor = self._draw_text_centered(
                draw, meta_line, y_cursor, w, self._font_meta, SUBTITLE_COLOR, pad
            )
            y_cursor -= 14

        # ── Season / Episode for series ───────────────────────────────────────
        if is_series and meta.get("season") is not None:
            se_text = f"Season {meta['season']:02d}  •  Episode {meta['episode']:02d}"
            y_cursor = self._draw_text_centered(
                draw, se_text, y_cursor, w, self._font_regular, SUBTITLE_COLOR, pad
            )
            y_cursor -= 20

        # ── Main title ────────────────────────────────────────────────────────
        font = self._fit_font(title, w - pad * 2, TITLE_FONT_MAX, TITLE_FONT_MIN)
        self._draw_text_centered(draw, title, y_cursor, w, font, TITLE_COLOR, pad)

        return img

    def _draw_text_centered(
        self, draw, text: str, bottom_y: int, canvas_w: int,
        font, color: tuple, pad: int
    ) -> int:
        """Draw text center-aligned above bottom_y; return new y (top of drawn text)."""
        bbox  = draw.textbbox((0, 0), text, font=font)
        tw    = bbox[2] - bbox[0]
        th    = bbox[3] - bbox[1]
        x     = (canvas_w - tw) // 2
        top_y = bottom_y - th

        # Shadow
        shadow_col = (0, 0, 0, 180)
        for dx, dy in [(-SHADOW_OFFSET, SHADOW_OFFSET), (SHADOW_OFFSET, SHADOW_OFFSET),
                       (0, SHADOW_OFFSET * 2)]:
            draw.text((x + dx, top_y + dy), text, font=font,
                      fill=shadow_col[:3] + (shadow_col[3],))

        draw.text((x, top_y), text, font=font, fill=color[:3] + (color[3],))
        return top_y - 8   # small gap above

    # ── Font helpers ──────────────────────────────────────────────────────────

    def _fit_font(self, text: str, max_width: int, max_size: int, min_size: int) -> ImageFont.FreeTypeFont:
        """Return the largest font size that fits text within max_width."""
        for size in range(max_size, min_size - 1, -2):
            font = self._load_font(Config.FONT_BOLD, size)
            tmp  = Image.new("RGBA", (1, 1))
            d    = ImageDraw.Draw(tmp)
            bbox = d.textbbox((0, 0), text, font=font)
            if bbox[2] - bbox[0] <= max_width:
                return font
        return self._load_font(Config.FONT_BOLD, min_size)

    @staticmethod
    def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            logger.warning("Could not load font '%s'; falling back to default.", path)
            return ImageFont.load_default()

    # ── Output path ───────────────────────────────────────────────────────────

    def _output_path(self, meta: dict) -> str:
        safe = meta["title"].replace(" ", "_").replace("/", "-")
        suffix = (
            f"_S{meta['season']:02d}E{meta['episode']:02d}"
            if meta.get("season") is not None else ""
        )
        return os.path.join(OUT_DIR, f"poster_{safe}{suffix}.jpg")
