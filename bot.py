import asyncio

# Initialize event loop before imports for compatibility
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

import math
import traceback
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery
)
from pyrogram.errors import UserNotParticipant, RPCError
from pyrogram.enums import ChatMemberStatus

# Kurigram Colored Button Styles
try:
    from pyrogram.enums import ButtonStyle
except ImportError:
    class ButtonStyle:
        PRIMARY = "primary"   # Telegram Blue
        SUCCESS = "success"   # Telegram Green
        DANGER = "danger"     # Telegram Red

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

def format_size(size_bytes: int) -> str:
    if not size_bytes:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

# Strict Force Subscribe Verification
async def check_fsub(client: Client, user_id: int):
    unjoined = []
    for ch in FSUB_CHANNELS:
        chat_id = ch.get("chat_id")
        if not chat_id or str(chat_id).startswith("-100111111111"):
            # Dummy/unset ID detected
            continue
        try:
            member = await client.get_chat_member(chat_id, user_id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                unjoined.append(ch)
        except UserNotParticipant:
            unjoined.append(ch)
        except Exception as e:
            print(f"! Error checking channel {chat_id} for user {user_id}: {e}")
            # If bot cannot check (e.g. not admin), require channel to protect links
            unjoined.append(ch)
    return unjoined

# 4-minute auto-deletion background task (240 seconds)
async def auto_delete_task(chat_id: int, message_id: int, delay_seconds: int = 240):
    await asyncio.sleep(delay_seconds)
    try:
        await bot.delete_messages(chat_id, message_id)
    except Exception:
        pass

def get_fsub_keyboard(unjoined_channels, file_hash: str):
    buttons = []
    for idx, ch in enumerate(unjoined_channels, start=1):
        buttons.append([
            InlineKeyboardButton(
                f"📢 Join Backup Channel {idx} ➜", 
                url=ch["link"], 
                style=ButtonStyle.PRIMARY
            )
        ])
    # Real-time Callback Verify Button
    buttons.append([
        InlineKeyboardButton(
            "🔄 Verify & Refresh Access 🔄", 
            callback_data=f"verify_{file_hash}", 
            style=ButtonStyle.SUCCESS
        )
    ])
    return InlineKeyboardMarkup(buttons)

@bot.on_message(filters.channel)
async def channel_post_listener(client: Client, message: Message):
    pass

@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    text_parts = message.text.split()
    file_hash = text_parts[1].replace("file_", "") if len(text_parts) > 1 and text_parts[1].startswith("file_") else ""

    # Step 1: Check Force Subscribe for all 4 channels
    unjoined = await check_fsub(client, user_id)
    if unjoined:
        return await message.reply_text(
            "🔒 **Access Denied!**\n\n"
            "To unlock this file, you must subscribe to our **4 backup channels** below.\n\n"
            "1. Join each channel listed below.\n"
            "2. Tap the **Verify & Refresh Access** button to get your download link.",
            reply_markup=get_fsub_keyboard(unjoined, file_hash)
        )

    # Step 2: Deliver file download link if subscribed
    if file_hash:
        file_data = await get_file(file_hash)
        if not file_data:
            return await message.reply_text("❌ **Link Expired or File Not Found!**")

        chrome_url = f"{FQDN}/chrome/{file_hash}"
        readable_size = format_size(file_data.get("file_size", 0))

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "⚡ FAST DOWNLOAD (CHROME) ⚡", 
                    url=chrome_url, 
                    style=ButtonStyle.SUCCESS
                )
            ]
        ])

        sent = await message.reply_text(
            f"🎬 **File Ready:** `{file_data['file_name']}`\n"
            f"💾 **Size:** `{readable_size}`\n\n"
            f"🔗 **Download Link:** [Click Here to Unlock]({chrome_url})\n\n"
            f"⚠️ **Notice:** Tapping the green button will automatically launch **Google Chrome** for high-speed multi-threaded downloading.\n"
            f"⏳ **Security Timer:** This button will automatically be deleted in **4 minutes**!",
            reply_markup=keyboard
        )

        asyncio.create_task(auto_delete_task(message.chat.id, sent.id, 240))
        return

    await message.reply_text(
        "👋 **Welcome to the Ultra-Fast File Stream & Link Bot!**\n\n"
        "Send files directly to generate high-speed download links.\n"
        "*(Note: File link generation is restricted to the bot owner)*"
    )

# Callback Handler for Instant Real-Time Verification
@bot.on_callback_query(filters.regex(r"^verify_(.*)"))
async def verify_callback_handler(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    file_hash = query.matches[0].group(1)

    unjoined = await check_fsub(client, user_id)
    if unjoined:
        await query.answer("❌ You haven't joined all 4 backup channels yet! Please join all of them.", show_alert=True)
        # Update buttons in case they joined some of them
        try:
            await query.message.edit_reply_markup(reply_markup=get_fsub_keyboard(unjoined, file_hash))
        except Exception:
            pass
        return

    await query.answer("✅ Verified successfully! Generating your link...", show_alert=False)

    if not file_hash:
        await query.message.edit_text("✅ **Verification Successful!** You now have full access to the bot.")
        return

    file_data = await get_file(file_hash)
    if not file_data:
        return await query.message.edit_text("❌ **Link Expired or File Not Found!**")

    chrome_url = f"{FQDN}/chrome/{file_hash}"
    readable_size = format_size(file_data.get("file_size", 0))

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⚡ FAST DOWNLOAD (CHROME) ⚡", 
                url=chrome_url, 
                style=ButtonStyle.SUCCESS
            )
        ]
    ])

    await query.message.edit_text(
        f"🎬 **File Ready:** `{file_data['file_name']}`\n"
        f"💾 **Size:** `{readable_size}`\n\n"
        f"🔗 **Download Link:** [Click Here to Unlock]({chrome_url})\n\n"
        f"⚠️ **Notice:** Tapping the green button will automatically launch **Google Chrome** for high-speed multi-threaded downloading.\n"
        f"⏳ **Security Timer:** This button will automatically be deleted in **4 minutes**!",
        reply_markup=keyboard
    )

    asyncio.create_task(auto_delete_task(query.message.chat.id, query.message.id, 240))

@bot.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def file_upload_handler(client: Client, message: Message):
    user_id = message.from_user.id

    if user_id != OWNER_ID:
        return await message.reply_text("⛔ **Unauthorized:** Only the bot owner can upload files.")

    media = getattr(message, message.media.value, None)
    if not media:
        return await message.reply_text("❌ **Unsupported media format.**")

    file_size = getattr(media, "file_size", 0)

    # 2GB Telegram API Bot limit check
    if file_size > 2000 * 1024 * 1024:
        size_gb = round(file_size / (1024 * 1024 * 1024), 2)
        return await message.reply_text(
            f"⚠️ **File Too Large ({size_gb} GB)!**\n\n"
            f"Telegram limits standard bots to files under **2.0 GB**.\n"
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
        direct_web_link = f"{FQDN}/chrome/{file_hash}"

        await status_msg.edit_text(
            f"✅ **File Stored Permanently!**\n\n"
            f"📁 **Name:** `{file_name}`\n"
            f"💾 **Size:** `{format_size(file_size)}`\n\n"
            f"🤖 **Bot Start Link:**\n`{deep_link}`\n\n"
            f"🌐 **Direct Chrome Web Link:**\n`{direct_web_link}`",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🚀 Test Download Link", 
                        url=deep_link, 
                        style=ButtonStyle.SUCCESS
                    )
                ]
            ])
        )
    except RPCError as e:
        await status_msg.edit_text(
            f"❌ **Telegram Error:** `{e.MESSAGE}`\n\n"
            f"Ensure the bot is added as **Admin** in `{DB_CHANNEL}` with **Post Messages** enabled."
        )
    except Exception as e:
        err_msg = traceback.format_exc()
        print(f"Error in upload handler: {err_msg}")
        await status_msg.edit_text(f"❌ **Server Error:** `{str(e)}`")

async def main():
    await bot.start()
    print("Bot started successfully!")

    # Pre-cache Storage Channel
    try:
        chat = await bot.get_chat(DB_CHANNEL)
        print(f"✓ Connected to Storage Channel: {chat.title} ({chat.id})")
    except Exception as e:
        print(f"! Storage Channel notice: {e}")

    # Pre-cache all 4 FSUB channels to prevent PeerIdInvalid
    for ch in FSUB_CHANNELS:
        c_id = ch.get("chat_id")
        try:
            fchat = await bot.get_chat(c_id)
            print(f"✓ Connected to Backup Channel: {fchat.title} ({c_id})")
        except Exception as e:
            print(f"! Warning: Failed to cache Backup Channel {c_id}: {e}")

    app = init_web_server(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Web server running on port {PORT} with URL {FQDN}")

    await asyncio.Event().wait()

if __name__ == "__main__":
    loop.run_until_complete(main())
