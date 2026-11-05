import asyncio

# Initialize event loop before importing Pyrogram for Python 3.11/3.14 compatibility
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

import traceback
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message
)
from pyrogram.errors import UserNotParticipant, RPCError, PeerIdInvalid, ChannelInvalid
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
            continue
    return unjoined

async def auto_delete_task(chat_id: int, message_id: int, delay_seconds: int = 240):
    await asyncio.sleep(delay_seconds)
    try:
        await bot.delete_messages(chat_id, message_id)
    except Exception:
        pass

# Automatically cache peer whenever a message is posted in the DB channel
@bot.on_message(filters.chat(DB_CHANNEL))
async def db_channel_listener(client: Client, message: Message):
    print(f"✓ DB Channel peer cached successfully: {message.chat.id}")

@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    text_parts = message.text.split()

    # Step 1: Force Subscribe check
    unjoined = await check_fsub(client, user_id)
    if unjoined:
        buttons = []
        for idx, ch in enumerate(FSUB_CHANNELS, start=1):
            buttons.append([InlineKeyboardButton(f"📢 Join Backup Channel {idx} ➜", url=ch["link"])])
        
        file_arg = text_parts[1] if len(text_parts) > 1 else ""
        buttons.append([InlineKeyboardButton("🔄 Verify & Refresh Access 🔄", url=f"https://t.me/{client.me.username}?start={file_arg}")])

        return await message.reply_text(
            "🔒 **Access Denied!**\n\n"
            "To access this file, subscribe to our **4 backup channels**.\n"
            "After joining all channels, click the **Verify & Refresh Access** button below.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # Step 2: Handle deep-link file access
    if len(text_parts) > 1 and text_parts[1].startswith("file_"):
        file_hash = text_parts[1].replace("file_", "")
        file_data = await get_file(file_hash)
        if not file_data:
            return await message.reply_text("❌ **Link Expired or File Not Found!**")

        step1_url = f"{FQDN}/step1/{file_hash}"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ FAST DOWNLOAD (CHROME) ⚡", url=step1_url)],
            [InlineKeyboardButton("🌐 Open Directly in Chrome Browser 🌐", url=step1_url)]
        ])

        sent = await message.reply_text(
            f"🎬 **File Ready:** `{file_data['file_name']}`\n\n"
            f"🔗 **Download Link:** [Click Here to Unlock]({step1_url})\n\n"
            f"⚠️ **Notice:** Open this link in **Google Chrome** for high-speed direct downloading.\n"
            f"⏳ **Security Timer:** This button will automatically be deleted in **4 minutes**!",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

        asyncio.create_task(auto_delete_task(message.chat.id, sent.id, 240))
        return

    await message.reply_text(
        "👋 **Welcome to the Ultra-Fast File Stream & Link Bot!**\n\n"
        "Send files directly to generate high-speed download links.\n"
        "*(Note: File link generation is restricted to the bot owner)*"
    )

# Forwarded channel handler to automatically link storage peer
@bot.on_message(filters.private & filters.forwarded)
async def forwarded_channel_link(client: Client, message: Message):
    if message.from_user.id != OWNER_ID:
        return

    if message.forward_from_chat:
        fwd_chat = message.forward_from_chat
        await message.reply_text(
            f"📡 **Channel Linked & Peer Cached!**\n\n"
            f"📌 **Title:** `{fwd_chat.title}`\n"
            f"🆔 **Channel ID:** `{fwd_chat.id}`\n\n"
            f"*(Make sure `DB_CHANNEL` in Render matches this ID exactly)*"
        )

@bot.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def file_upload_handler(client: Client, message: Message):
    user_id = message.from_user.id

    if user_id != OWNER_ID:
        return await message.reply_text("⛔ **Unauthorized:** Only the bot owner can upload files.")

    media = getattr(message, message.media.value, None)
    if not media:
        return await message.reply_text("❌ **Unsupported media format.**")

    file_size = getattr(media, "file_size", 0)

    # Telegram bot 2GB limit check
    if file_size > 2000 * 1024 * 1024:
        size_gb = round(file_size / (1024 * 1024 * 1024), 2)
        return await message.reply_text(
            f"⚠️ **File Too Large ({size_gb} GB)!**\n\n"
            f"Telegram strictly limits bots to files under **2.0 GB**.\n"
            f"Please compress or split this file under 2 GB to stream."
        )

    file_name = getattr(media, "file_name", None)
    if not file_name:
        ext = ".mp4" if message.video else (".mp3" if message.audio else "")
        file_name = f"file_{message.id}{ext}"

    mime_type = getattr(media, "mime_type", "application/octet-stream")

    status_msg = await message.reply_text("🔄 **Forwarding to Unlimited Storage Channel...**")

    try:
        copied_msg = await message.copy(DB_CHANNEL)
        file_hash = await save_file(copied_msg.id, file_name, file_size, mime_type)
        bot_username = client.me.username

        deep_link = f"https://t.me/{bot_username}?start=file_{file_hash}"
        direct_web_link = f"{FQDN}/step1/{file_hash}"

        await status_msg.edit_text(
            f"✅ **File Stored Permanently!**\n\n"
            f"📁 **Name:** `{file_name}`\n"
            f"💾 **Size:** `{round(file_size / (1024 * 1024), 2)} MB`\n\n"
            f"🤖 **Bot Start Link:**\n`{deep_link}`\n\n"
            f"🌐 **Direct Shortener Web Link:**\n`{direct_web_link}`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Test Download Link", url=deep_link)]
            ])
        )
    except (PeerIdInvalid, ChannelInvalid):
        await status_msg.edit_text(
            f"❌ **Peer ID Invalid:** The bot has not cached channel `{DB_CHANNEL}` yet.\n\n"
            f"**To fix in 5 seconds:**\n"
            f"1. Open your private storage channel.\n"
            f"2. Send any message there (e.g. `hi`).\n"
            f"3. Forward that message to this bot chat.\n"
            f"4. Re-upload your file!"
        )
    except RPCError as e:
        await status_msg.edit_text(
            f"❌ **Telegram Error:** `{e.MESSAGE}`\n\n"
            f"Ensure the bot is an **Admin** in channel `{DB_CHANNEL}` with **Post Messages** enabled."
        )
    except Exception as e:
        err_msg = traceback.format_exc()
        print(f"Error in upload handler: {err_msg}")
        await status_msg.edit_text(f"❌ **Error:** `{str(e)}`")

async def main():
    await bot.start()
    print("Bot started successfully!")

    # Pre-resolve the channel if accessible
    try:
        chat = await bot.get_chat(DB_CHANNEL)
        print(f"✓ Connected to Storage Channel: {chat.title} ({chat.id})")
    except Exception as e:
        print(f"! Storage Channel not yet cached in session: {e}")

    app = init_web_server(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Web server running on port {PORT} with URL {FQDN}")

    await asyncio.Event().wait()

if __name__ == "__main__":
    loop.run_until_complete(main())
