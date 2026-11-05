import os

# Telegram API Credentials (Get from https://my.telegram.org)
API_ID = int(os.environ.get("API_ID", "1234567"))
API_HASH = os.environ.get("API_HASH", "your_api_hash_here")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token_here")

# Bot Owner Telegram ID (Only this ID can upload files to prevent misuse)
OWNER_ID = int(os.environ.get("OWNER_ID", "123456789"))

# Telegram Private Channel Storage ID (Add your bot as Admin with full rights)
# Example: -1001234567890
DB_CHANNEL = int(os.environ.get("DB_CHANNEL", "-1000000000000"))

# 4 Force-Subscribe Channels (Channel ID, Invite/Public Link)
# Bot MUST be an Admin in all 4 channels to check member status!
FSUB_CHANNELS = [
    {"chat_id": int(os.environ.get("FSUB_1_ID", "-1001111111111")), "link": os.environ.get("FSUB_1_LINK", "https://t.me/backup_channel_1")},
    {"chat_id": int(os.environ.get("FSUB_2_ID", "-1002222222222")), "link": os.environ.get("FSUB_2_LINK", "https://t.me/backup_channel_2")},
    {"chat_id": int(os.environ.get("FSUB_3_ID", "-1003333333333")), "link": os.environ.get("FSUB_3_LINK", "https://t.me/backup_channel_3")},
    {"chat_id": int(os.environ.get("FSUB_4_ID", "-1004444444444")), "link": os.environ.get("FSUB_4_LINK", "https://t.me/backup_channel_4")},
]

# MongoDB URI (Free tier from cloud.mongodb.com)
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority")
DATABASE_NAME = os.environ.get("DATABASE_NAME", "FileStreamBot")

# Web Server & Domain Configuration
PORT = int(os.environ.get("PORT", 8080))
FQDN = os.environ.get("FQDN", "https://your-app-name.onrender.com").rstrip("/")
