"""
modules/filename_parser.py
─────────────────────────
Extracts structured metadata from raw media filenames.

Supported patterns
  Movie   : Rajadrohi.2025.1080p.HDRip.mkv
  Series  : Beast.Games.S02E06.720p.WEB-DL.mkv
"""

import re
from dataclasses import dataclass, field
from typing import Optional


# ── Regex Patterns ────────────────────────────────────────────────────────────

_RE_SERIES     = re.compile(r"[Ss](\d{1,2})[Ee](\d{1,2})")
_RE_YEAR       = re.compile(r"\b(20[0-2]\d)\b")
_RE_QUALITY    = re.compile(r"\b(480p|720p|1080p|2160p|4K)\b", re.IGNORECASE)
_RE_RIP_TYPE   = re.compile(
    r"\b(HDRip|WEB-DL|WEBRip|BluRay|BDRip|DVDRip|HDTV|AMZN|NF|DSNP|SonyLIV|ZEE5|Hotstar)\b",
    re.IGNORECASE,
)
_RE_CODEC      = re.compile(
    r"\b(x264|x265|H264|H265|HEVC|AVC|10bit|HDR|SDR|DV|DoVi)\b",
    re.IGNORECASE,
)
_RE_AUDIO      = re.compile(
    r"\b(AAC|DD5\.1|DDP5\.1|DTS|AC3|TrueHD|Atmos|FLAC|MP3|2\.0|5\.1|7\.1)\b",
    re.IGNORECASE,
)
_RE_LANGUAGE   = re.compile(
    r"\b(Hindi|Tamil|Telugu|Malayalam|Kannada|Bengali|English|Multi|Dual|ORG|UNCUT)\b",
    re.IGNORECASE,
)
_RE_EXTENSION  = re.compile(r"\.(mkv|mp4|avi|mov|ts|m2ts|flv)$", re.IGNORECASE)
_RE_JUNK_TAGS  = re.compile(
    r"\b(www\.\S+|Download|REPACK|PROPER|INTERNAL|Extended|Theatrical|Directors\.Cut|"
    r"Criterion|Remux|UHD|SDR|IMAX|3D|SBS|HOU|DUBBED|SUBBED|ESub|MSub|HardSub)\b",
    re.IGNORECASE,
)
_RE_DOTS_DASHES = re.compile(r"[\._\-]+")


@dataclass
class MediaMeta:
    raw_filename: str
    title: str          = ""
    year: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    quality: str        = ""
    rip_type: str       = ""
    codec: str          = ""
    audio: str          = ""
    languages: list     = field(default_factory=list)
    media_type: str     = "movie"   # "movie" | "series"
    extension: str      = ""

    @property
    def display_quality(self) -> str:
        parts = [p for p in [self.quality, self.rip_type] if p]
        return " | ".join(parts) if parts else "Unknown"

    def to_dict(self) -> dict:
        return {
            "raw_filename": self.raw_filename,
            "title":        self.title,
            "year":         self.year,
            "season":       self.season,
            "episode":      self.episode,
            "quality":      self.quality,
            "rip_type":     self.rip_type,
            "codec":        self.codec,
            "audio":        self.audio,
            "languages":    self.languages,
            "media_type":   self.media_type,
            "extension":    self.extension,
        }


class FilenameParser:
    """Parse a raw media filename into structured metadata."""

    def parse(self, filename: str) -> dict:
        meta = MediaMeta(raw_filename=filename)

        # Strip extension
        ext_m = _RE_EXTENSION.search(filename)
        if ext_m:
            meta.extension = ext_m.group(1).lower()
            filename = filename[: ext_m.start()]

        # Series detection
        series_m = _RE_SERIES.search(filename)
        if series_m:
            meta.media_type = "series"
            meta.season  = int(series_m.group(1))
            meta.episode = int(series_m.group(2))

        # Year
        year_m = _RE_YEAR.search(filename)
        if year_m:
            meta.year = int(year_m.group(1))

        # Quality / rip / codec / audio / language
        q_m = _RE_QUALITY.search(filename)
        if q_m:
            meta.quality = q_m.group(1).upper()

        r_m = _RE_RIP_TYPE.search(filename)
        if r_m:
            meta.rip_type = r_m.group(1)

        c_m = _RE_CODEC.search(filename)
        if c_m:
            meta.codec = c_m.group(1)

        a_m = _RE_AUDIO.search(filename)
        if a_m:
            meta.audio = a_m.group(1)

        meta.languages = list({m.group(1).title() for m in _RE_LANGUAGE.finditer(filename)})

        # ── Clean title ───────────────────────────────────────────────────────
        title = filename

        # Remove series marker and everything after
        if series_m:
            title = title[: series_m.start()]

        # Remove year and everything after if no series marker removed them
        elif year_m:
            title = title[: year_m.start()]

        # Remove known tags
        for pattern in [_RE_QUALITY, _RE_RIP_TYPE, _RE_CODEC, _RE_AUDIO,
                        _RE_LANGUAGE, _RE_JUNK_TAGS, _RE_YEAR]:
            title = pattern.sub(" ", title)

        # Normalise separators → spaces
        title = _RE_DOTS_DASHES.sub(" ", title)

        # Title-case and strip
        meta.title = " ".join(title.split()).title()

        return meta.to_dict()
