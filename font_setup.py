"""
modules/font_setup.py
─────────────────────
Downloads DejaVu fonts at startup if not already present.
Works on any platform (Koyeb, Heroku, Render, VPS).
"""
import os
import logging
import urllib.request
import tarfile

logger = logging.getLogger("FontSetup")

FONT_URL  = "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.tar.bz2"
FONT_DIR  = "assets/fonts"
BOLD_DST  = os.path.join(FONT_DIR, "bold.ttf")
REG_DST   = os.path.join(FONT_DIR, "regular.ttf")


def ensure_fonts():
    if os.path.exists(BOLD_DST) and os.path.exists(REG_DST):
        return  # Already present

    os.makedirs(FONT_DIR, exist_ok=True)
    logger.info("📥 Downloading DejaVu fonts...")

    tmp = "/tmp/dejavu.tar.bz2"
    try:
        urllib.request.urlretrieve(FONT_URL, tmp)
        with tarfile.open(tmp, "r:bz2") as tar:
            for member in tar.getmembers():
                if member.name.endswith("DejaVuSans-Bold.ttf"):
                    member.name = os.path.basename(member.name)
                    tar.extract(member, FONT_DIR)
                    os.rename(os.path.join(FONT_DIR, member.name), BOLD_DST)
                elif member.name.endswith("DejaVuSans.ttf"):
                    member.name = os.path.basename(member.name)
                    tar.extract(member, FONT_DIR)
                    os.rename(os.path.join(FONT_DIR, member.name), REG_DST)
        logger.info("✅ Fonts installed: %s, %s", BOLD_DST, REG_DST)
    except Exception as e:
        logger.warning("⚠️  Font download failed (%s) — will use default font", e)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
