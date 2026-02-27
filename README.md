# 🎬 Telegram Auto Post Bot
### Auto Poster Generator + Auto Post System
**Stack:** Python 3.11 • Pyrogram • MongoDB • TMDB API • Pillow**

---

## ✨ Features

| Feature | Detail |
|---|---|
| 🔍 Smart filename parsing | Title, year, season, episode, quality, audio, language |
| 🎨 Premium poster generation | 1080 px HD, dark gradient, Netflix-style typography |
| 📡 TMDB Integration | Auto-searches movie/TV database, downloads original poster |
| 💾 Poster caching | MongoDB cache — never re-fetches the same poster twice |
| 🌐 Multi-language | Detects Hindi, Tamil, Telugu, Malayalam, Kannada, English + more |
| 📺 Series support | Inline quality buttons per episode |
| 🎬 Movie support | Size + quality buttons + "Get All" link |
| 📌 Manual poster override | Upload photo before file → bot uses your poster |
| 🐳 Docker ready | One-command deploy anywhere |
| ☁️ Render.com ready | `render.yaml` included |

---

## 📁 Project Structure

```
telegram_autopost_bot/
├── main.py                  ← Entry point / event handlers
├── modules/
│   ├── config.py            ← Environment config
│   ├── filename_parser.py   ← Parse raw filenames → structured meta
│   ├── tmdb_client.py       ← Async TMDB API + poster download
│   ├── poster_generator.py  ← Pillow poster creation engine
│   ├── post_formatter.py    ← Caption + InlineKeyboard builder
│   └── database.py          ← MongoDB async wrapper (motor)
├── assets/
│   ├── fonts/
│   │   ├── bold.ttf         ← Poster title font  (add manually)
│   │   └── regular.ttf      ← Poster subtitle font
│   └── fallback.jpg         ← Fallback poster background
├── posters/                 ← Generated poster cache (auto-created)
├── scripts/
│   ├── test_parser.py       ← Smoke test for filename parser
│   └── setup_fonts.sh       ← Downloads free DejaVu fonts
├── requirements.txt
├── .env.example
├── Dockerfile
└── render.yaml
```

---

## 🚀 Quick Start

### Step 1 — Clone & configure

```bash
git clone https://github.com/youruser/telegram-autopost-bot.git
cd telegram-autopost-bot
cp .env.example .env
nano .env   # Fill in your credentials
```

### Step 2 — Add fonts

```bash
bash scripts/setup_fonts.sh
```

Or manually place any TTF fonts as:
- `assets/fonts/bold.ttf`
- `assets/fonts/regular.ttf`

### Step 3 — Install dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 4 — Test the parser (no credentials needed)

```bash
python scripts/test_parser.py
```

### Step 5 — Run the bot

```bash
python main.py
```

---

## 🔑 Environment Variables

| Variable | Description | Required |
|---|---|---|
| `BOT_TOKEN` | From @BotFather | ✅ |
| `API_ID` | From my.telegram.org | ✅ |
| `API_HASH` | From my.telegram.org | ✅ |
| `SOURCE_CHANNEL_ID` | Channel where you upload files | ✅ |
| `DEST_CHANNEL_ID` | Public channel for posts | ✅ |
| `TMDB_API_KEY` | Free from themoviedb.org | ✅ |
| `MONGO_URI` | MongoDB Atlas connection string | ✅ |
| `MONGO_DB_NAME` | Database name (default: `autopostbot`) | ❌ |
| `POSTER_OUTPUT_DIR` | Local folder for posters (default: `posters/`) | ❌ |

---

## 📋 Step-by-Step Credentials Setup

### Telegram API (API_ID + API_HASH)
1. Go to [my.telegram.org](https://my.telegram.org)
2. Log in with your phone number
3. Click **"API development tools"**
4. Create a new application
5. Copy `api_id` and `api_hash`

### Bot Token
1. Open Telegram → search **@BotFather**
2. Send `/newbot`
3. Follow instructions → copy the token
4. **Add your bot as admin** to both SOURCE and DEST channels

### TMDB API Key (Free)
1. Register at [themoviedb.org](https://www.themoviedb.org/signup)
2. Go to **Settings → API → Create**
3. Select "Developer" → fill the form (can use localhost as URL)
4. Copy the **API Key (v3 auth)**

### MongoDB Atlas (Free Tier)
1. Sign up at [cloud.mongodb.com](https://cloud.mongodb.com)
2. Create a free M0 cluster (Singapore region recommended)
3. Create a database user (Settings → Database Access)
4. Whitelist `0.0.0.0/0` in Network Access
5. Click "Connect" → "Connect your application" → copy the URI
6. Replace `<password>` with your user's password

### Channel IDs
```
# Method 1: Forward a message from the channel to @userinfobot
# Method 2: Use web.telegram.org → the URL shows the ID
# Always prefix with -100 for supergroups/channels
# e.g. channel ID 1234567890 → SOURCE_CHANNEL_ID=-1001234567890
```

---

## ☁️ Deploy on Render.com

1. Push your code to GitHub
2. Go to [render.com](https://render.com) → **New → Blueprint**
3. Connect your repository
4. Render will detect `render.yaml` automatically
5. Fill in environment variables in the Render dashboard
6. Click **Deploy**

> ⚠️ Set `POSTER_OUTPUT_DIR=/tmp/posters` on Render (ephemeral disk).
> Use the Render persistent disk feature if you need poster persistence across deploys.

---

## 🐳 Deploy on VPS (Docker)

```bash
# 1. Clone repo on your VPS
git clone https://github.com/youruser/telegram-autopost-bot.git
cd telegram-autopost-bot

# 2. Copy and fill env file
cp .env.example .env
nano .env

# 3. Build and run
docker build -t autopostbot .
docker run -d \
  --name autopostbot \
  --restart unless-stopped \
  --env-file .env \
  -v $(pwd)/posters:/app/posters \
  autopostbot

# 4. View logs
docker logs -f autopostbot
```

---

## 🧪 How It Works — Full Flow

```
1. You upload file to SOURCE channel
         ↓
2. Bot reads filename
   "Beast.Games.S02E06.720p.WEB-DL.mkv"
         ↓
3. FilenameParser extracts:
   title="Beast Games", season=2, episode=6,
   quality="720P", rip_type="WEB-DL", type=series
         ↓
4. MongoDB check: Is poster cached?
   YES → use cached path
   NO  → search TMDB
         ↓
5. TMDBClient searches TV/Movie endpoint
   Downloads original poster image
         ↓
6. PosterGenerator:
   - Resize to 1080 px wide
   - Apply dark gradient overlay
   - Draw title + S/E info with shadow
   - Save as JPEG
         ↓
7. PostFormatter builds:
   - Caption with emoji metadata
   - InlineKeyboard with quality buttons
         ↓
8. Bot posts to DEST channel:
   [Poster image] + [Caption] + [Buttons]
   Then forwards the original file
```

---

## 💡 Tips & Troubleshooting

| Problem | Fix |
|---|---|
| Bot not receiving messages | Make sure bot is **admin** in SOURCE channel |
| TMDB returns no results | Try shorter, cleaner title in caption |
| Poster looks blurry | Ensure `assets/fonts/` has valid TTF files |
| MongoDB connection fails | Check IP whitelist (allow 0.0.0.0/0) |
| Pyrogram session error | Delete `auto_post_bot.session` and restart |
| Fonts not rendering | Run `bash scripts/setup_fonts.sh` |

---

## 📊 MongoDB Schema Reference

### `poster_cache` collection
```json
{
  "_id": "ObjectId",
  "title": "beast games",
  "year": 2024,
  "media_type": "series",
  "poster_path": "posters/poster_Beast_Games_S02E06.jpg",
  "tmdb_data": { "tmdb_id": 12345, "vote_average": 8.2, ... },
  "updated_at": "ISODate"
}
```

### `manual_posters` collection
```json
{
  "_id": "ObjectId",
  "hint": "beast games",
  "file_id": "AgACAgIAAxk...",
  "saved_at": "ISODate"
}
```

### `posted_files` collection
```json
{
  "_id": "ObjectId",
  "message_id": 1234,
  "title": "Beast Games",
  "posted_at": "ISODate"
}
```

---

## 🛡 License
MIT — Free to use, modify, and deploy.
