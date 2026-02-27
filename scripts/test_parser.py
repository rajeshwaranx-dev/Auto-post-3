#!/usr/bin/env python3
"""
scripts/test_parser.py — Quick smoke-test for FilenameParser.
Run: python scripts/test_parser.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.filename_parser import FilenameParser

parser = FilenameParser()

SAMPLES = [
    "Rajadrohi.2025.1080p.HDRip.mkv",
    "Beast.Games.S02E06.720p.WEB-DL.mkv",
    "Pushpa.2.The.Rule.2024.2160p.AMZN.WEB-DL.DDP5.1.Atmos.x265.Hindi.mkv",
    "The.Last.of.Us.S01E01.720p.BluRay.x264.AAC.English.mkv",
    "KGF.Chapter.2.2022.1080p.BluRay.DD5.1.x265.HEVC.Tamil.Telugu.Kannada.Hindi.mkv",
    "Leo.2023.1080p.WEB-DL.AAC.Tamil.mkv",
]

print("=" * 70)
for fn in SAMPLES:
    meta = parser.parse(fn)
    print(f"\n📁 {fn}")
    print(f"   title      : {meta['title']}")
    print(f"   year       : {meta['year']}")
    print(f"   type       : {meta['media_type']}")
    print(f"   season/ep  : {meta['season']} / {meta['episode']}")
    print(f"   quality    : {meta['quality']}")
    print(f"   rip_type   : {meta['rip_type']}")
    print(f"   audio      : {meta['audio']}")
    print(f"   languages  : {meta['languages']}")
print("=" * 70)
