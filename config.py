import os

def parse_chat(key: str, default=None):
    val = str(os.environ.get(key, default or "")).strip()
    if not val:
        return None
    if val.startswith("@"):
        return val
    try:
        return int(val)
    except ValueError:
        return val

# Telegram Bot Credentials
API_ID = int(os.environ.get("API_ID", "1234567"))
API_HASH = os.environ.get("API_HASH", "your_api_hash_here")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token_here")

# Owner Telegram User ID
OWNER_ID = int(os.environ.get("OWNER_ID", "123456789"))

# Storage Channel (Username or -100 ID)
DB_CHANNEL = parse_chat("DB_CHANNEL", "-1000000000000")

# Optional Pyrogram String Session for 4GB Streaming
USER_SESSION_STRING = os.environ.get("USER_SESSION_STRING", "").strip()

# 4 Force-Subscribe Channel IDs
FSUB_CHANNELS = [
    {"chat_id": parse_chat("FSUB_1_ID"), "link": os.environ.get("FSUB_1_LINK", "").strip()},
    {"chat_id": parse_chat("FSUB_2_ID"), "link": os.environ.get("FSUB_2_LINK", "").strip()},
    {"chat_id": parse_chat("FSUB_3_ID"), "link": os.environ.get("FSUB_3_LINK", "").strip()},
    {"chat_id": parse_chat("FSUB_4_ID"), "link": os.environ.get("FSUB_4_LINK", "").strip()},
]

# MongoDB URI & Settings
MONGO_URI = os.environ.get("MONGO_URI", "")
DATABASE_NAME = os.environ.get("DATABASE_NAME", "FileStreamBot")

# Web Server & Permanent Domain Configuration
PORT = int(os.environ.get("PORT", 8080))
# If using Cloudflare Worker proxy, set FQDN to your worker URL:
FQDN = os.environ.get("FQDN", "https://telegram-file-streamer-3vsl.onrender.com").rstrip("/")
