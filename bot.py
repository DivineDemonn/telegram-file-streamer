import asyncio
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery
)
from pyrogram.errors import UserNotParticipant, FloodWait
from pyrogram.enums import ChatMemberStatus

from config import (
    API_ID,
    API_HASH,
    BOT_TOKEN,
    OWNER_ID,
    DB_CHANNEL,
    FSUB_CHANNELS,
    FQDN,
    PORT
)
from database import save_file, get_file
from server import init_web_server
from aiohttp import web

bot = Client(
    "FastFileStreamBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Helper function to check all 4 channels
async def check_fsub(client: Client, user_id: int):
    unjoined = []
    for ch in FSUB_CHANNELS:
        try:
            member = await client.get_chat_member(ch["chat_id"], user_id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                unjoined.append(ch)
        except UserNotParticipant:
            unjoined.append(ch)
        except Exception:
            # If bot hasn't joined or lack permissions, treat as bypass or unjoined
            continue
    return unjoined

# Background task to delete message after 4 minutes (240 seconds)
async def auto_delete_task(chat_id: int, message_id: int, delay_seconds: int = 240):
    await asyncio.sleep(delay_seconds)
    try:
        await bot.delete_messages(chat_id, message_id)
    except Exception:
        pass

@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    text_parts = message.text.split()

    # Step 1: Check Force Subscribe for all 4 channels
    unjoined = await check_fsub(client, user_id)
    if unjoined:
        buttons = []
        for idx, ch in enumerate(FSUB_CHANNELS, start=1):
            buttons.append([InlineKeyboardButton(f"📢 Join Backup Channel {idx} ➜", url=ch["link"])])
        
        # Verify button reapplies the file command
        file_arg = text_parts[1] if len(text_parts) > 1 else ""
        buttons.append([InlineKeyboardButton("🔄 Verify & Refresh Access 🔄", url=f"https://t.me/{client.me.username}?start={file_arg}")])

        return await message.reply_text(
            "🔒 **Access Denied!**\n\n"
            "To access this file, you must subscribe to our **4 backup channels**.\n"
            "After joining all channels, click the **Verify & Refresh Access** button below.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # Step 2: Handle deep-link access (start=file_<hash>)
    if len(text_parts) > 1 and text_parts[1].startswith("file_"):
        file_hash = text_parts[1].replace("file_", "")
        file_data = await get_file(file_hash)
        if not file_data:
            return await message.reply_text("❌ **Link Expired or File Not Found!**")

        step1_url = f"{FQDN}/step1/{file_hash}"

        # Highly styled download button with dynamic indicators
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ FAST DOWNLOAD (CHROME) ⚡", url=step1_url)],
            [InlineKeyboardButton("🌐 Open Directly in Chrome Browser 🌐", url=step1_url)]
        ])

        sent = await message.reply_text(
            f"🎬 **File Ready:** `{file_data['file_name']}`\n\n"
            f"🔗 **Download Link:** [Click Here to Unlock]({step1_url})\n\n"
            f"⚠️ **Notice:** Open this link inside **Google Chrome** for multi-thread high-speed downloading.\n"
            f"⏳ **Security Timer:** This button and link will automatically be deleted in **4 minutes**!",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

        # Trigger auto-delete in 240 seconds
        asyncio.create_task(auto_delete_task(message.chat.id, sent.id, 240))
        return

    # Regular welcome message
    await message.reply_text(
        "👋 **Welcome to the Ultra-Fast File Stream & Link Bot!**\n\n"
        "Send files directly to receive high-speed download links.\n"
        "*(Note: File link generation is restricted to the bot owner)*"
    )

@bot.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def file_upload_handler(client: Client, message: Message):
    user_id = message.from_user.id

    # Restrict uploads strictly to the bot owner
    if user_id != OWNER_ID:
        return await message.reply_text("⛔ **Unauthorized:** Only the bot owner can upload files to this bot.")

    status_msg = await message.reply_text("🔄 **Forwarding to Unlimited Storage Channel...**")

    # Forward or copy to database channel
    media = getattr(message, message.media.value)
    copied_msg = await message.copy(DB_CHANNEL)

    file_name = getattr(media, "file_name", "telegram_file")
    file_size = getattr(media, "file_size", 0)
    mime_type = getattr(media, "mime_type", "application/octet-stream")

    file_hash = await save_file(copied_msg.id, file_name, file_size, mime_type)
    bot_username = client.me.username

    deep_link = f"https://t.me/{bot_username}?start=file_{file_hash}"
    direct_web_link = f"{FQDN}/step1/{file_hash}"

    await status_msg.edit_text(
        f"✅ **File Stored Permanently!**\n\n"
        f"📁 **Name:** `{file_name}`\n"
        f"💾 **Size:** `{round(file_size / (1024*1024), 2)} MB`\n\n"
        f"🤖 **Bot Start Link:**\n`{deep_link}`\n\n"
        f"🌐 **Direct Shortener Web Link:**\n`{direct_web_link}`\n\n"
        f"*(Users will verify 4 channels, pass through 2 countdown pages with Adsterra ads, and download in Chrome at full speed)*",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Test Download Link", url=deep_link)]
        ])
    )

async def main():
    await bot.start()
    print("Bot started successfully!")

    # Setup web application
    app = init_web_server(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Web server running on port {PORT} with URL {FQDN}")

    # Keep bot running
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
