import os

# Helper to automatically support both @usernames and numeric IDs
def parse_chat(value: str, default: str = ""):
    val = str(os.environ.get(value, default)).strip()
    if val.startswith("@"):
        return val
    try:
        return int(val)
    except ValueError:
        return val

# Telegram API Credentials
API_ID = int(os.environ.get("API_ID", "1234567"))
API_HASH = os.environ.get("API_HASH", "your_api_hash_here")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token_here")

# Owner Telegram User ID
OWNER_ID = int(os.environ.get("OWNER_ID", "123456789"))

# Telegram Storage Channel (Supports @username or -100xxxxxxxxxx)
DB_CHANNEL = parse_chat("DB_CHANNEL", "-1000000000000")

# 4 Force-Subscribe Channels (Supports both @username or numeric ID)
FSUB_CHANNELS = [
    {"chat_id": parse_chat("FSUB_1_ID", "-1001111111111"), "link": os.environ.get("FSUB_1_LINK", "https://t.me/backup_channel_1")},
    {"chat_id": parse_chat("FSUB_2_ID", "-1002222222222"), "link": os.environ.get("FSUB_2_LINK", "https://t.me/backup_channel_2")},
    {"chat_id": parse_chat("FSUB_3_ID", "-1003333333333"), "link": os.environ.get("FSUB_3_LINK", "https://t.me/backup_channel_3")},
    {"chat_id": parse_chat("FSUB_4_ID", "-1004444444444"), "link": os.environ.get("FSUB_4_LINK", "https://t.me/backup_channel_4")},
]

# MongoDB URI
MONGO_URI = os.environ.get("MONGO_URI", "")
DATABASE_NAME = os.environ.get("DATABASE_NAME", "FileStreamBot")

# Web Server & Domain
PORT = int(os.environ.get("PORT", 8080))
FQDN = os.environ.get("FQDN", "https://telegram-file-streamer-3vsl.onrender.com").rstrip("/")
