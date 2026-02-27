"""
modules/post_formatter.py
──────────────────────────
Builds caption text and InlineKeyboardMarkup for Telegram posts.
"""

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message


class PostFormatter:

    def build(self, meta: dict, message: Message) -> tuple[str, InlineKeyboardMarkup]:
        if meta["media_type"] == "series":
            return self._build_series(meta, message)
        return self._build_movie(meta, message)

    # ── Series ────────────────────────────────────────────────────────────────

    def _build_series(self, meta: dict, message: Message) -> tuple[str, InlineKeyboardMarkup]:
        title   = meta["title"]
        season  = meta.get("season")
        episode = meta.get("episode")
        quality = meta.get("rip_type") or meta.get("quality", "Unknown")
        year    = meta.get("year", "")
        lang    = ", ".join(meta.get("languages", [])) or "—"
        audio   = meta.get("audio", "—")

        s_fmt = f"{season:02d}"  if season  is not None else "?"
        e_fmt = f"{episode:02d}" if episode is not None else "?"

        caption = (
            f"🎬 **Title:** {title}\n"
            f"🗂 **Season:** {s_fmt}\n"
            f"📺 **Episode:** {e_fmt}\n"
            f"📀 **Quality:** {quality}\n"
            f"📅 **Year:** {year}\n"
            f"🌐 **Language:** {lang}\n"
            f"🎵 **Audio:** {audio}\n\n"
            f"🔥 **Telegram File** 🔥"
        )

        # Quality buttons row
        qualities = ["480P", "720P", "1080P"]
        file_id   = message.id
        buttons = [
            InlineKeyboardButton(f"EP{e_fmt} • {q}", callback_data=f"dl_{file_id}_{q}")
            for q in qualities
        ]

        keyboard = InlineKeyboardMarkup(
            [buttons[:3]]   # one row of 3
        )
        return caption, keyboard

    # ── Movie ─────────────────────────────────────────────────────────────────

    def _build_movie(self, meta: dict, message: Message) -> tuple[str, InlineKeyboardMarkup]:
        title   = meta["title"]
        year    = meta.get("year", "")
        quality = meta.get("rip_type") or meta.get("quality", "Unknown")
        lang    = ", ".join(meta.get("languages", [])) or "—"
        audio   = meta.get("audio", "—")
        codec   = meta.get("codec", "—")

        caption = (
            f"🎬 **Title:** {title}\n"
            f"📅 **Year:** {year}\n"
            f"📀 **Quality:** {quality}\n"
            f"🌐 **Language:** {lang}\n"
            f"🎵 **Audio:** {audio}\n"
            f"💾 **Codec:** {codec}\n\n"
            f"🔥 **Telegram File** 🔥"
        )

        file_id = message.id
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔥 480MB",  callback_data=f"dl_{file_id}_480"),
                InlineKeyboardButton("🔥 700MB",  callback_data=f"dl_{file_id}_700"),
            ],
            [
                InlineKeyboardButton("🔥 720p",   callback_data=f"dl_{file_id}_720p"),
                InlineKeyboardButton("🔥 1080p",  callback_data=f"dl_{file_id}_1080p"),
            ],
            [
                InlineKeyboardButton("📦 Get All Files", callback_data=f"all_{file_id}"),
            ],
        ])
        return caption, keyboard
