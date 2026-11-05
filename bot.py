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
    PORT,
    USER_SESSION_STRING
)
from database import save_file, get_file
from server import init_web_server
from aiohttp import web

# Main Bot Client (Commands, ForceSub, Buttons)
bot = Client(
    "FastFileStreamBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# User Client for 4GB high-speed downloading (Optional)
user_bot = None
if USER_SESSION_STRING:
    user_bot = Client(
        "UserStreamClient",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=USER_SESSION_STRING,
        no_updates=True
    )

FSUB_CACHE = {}

def format_size(size_bytes: int) -> str:
    if not size_bytes:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

async def refresh_fsub_cache(client: Client):
    """Auto-fetches channel titles and generates permanent invite links."""
    for item in FSUB_CHANNELS:
        c_id = item.get("chat_id")
        if not c_id:
            continue

        env_link = item.get("link", "")
        try:
            chat = await client.get_chat(c_id)
            title = chat.title or f"Backup Channel"

            if chat.username:
                real_link = f"https://t.me/{chat.username}"
            elif env_link and "backup_channel" not in env_link:
                real_link = env_link
            elif chat.invite_link:
                real_link = chat.invite_link
            else:
                try:
                    real_link = await client.export_chat_invite_link(c_id)
                except Exception:
                    new_inv = await client.create_chat_invite_link(c_id)
                    real_link = new_inv.invite_link

            FSUB_CACHE[c_id] = {
                "chat_id": c_id,
                "title": title,
                "link": real_link
            }
            print(f"✓ Channel Cached: '{title}' ({c_id}) -> {real_link}")

        except Exception as e:
            print(f"! Warning: Could not resolve channel {c_id}: {e}")
            if env_link and "backup_channel" not in env_link:
                FSUB_CACHE[c_id] = {
                    "chat_id": c_id,
                    "title": "Backup Channel",
                    "link": env_link
                }

async def check_fsub(client: Client, user_id: int):
    """Checks subscription status against all configured channels."""
    if not FSUB_CACHE:
        await refresh_fsub_cache(client)

    unjoined = []
    for c_id, ch_data in FSUB_CACHE.items():
        try:
            member = await client.get_chat_member(c_id, user_id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                unjoined.append(ch_data)
        except UserNotParticipant:
            unjoined.append(ch_data)
        except Exception as e:
            print(f"User {user_id} check failed in {c_id}: {e}")
            unjoined.append(ch_data)
    return unjoined

# 4-minute auto-deletion task
async def auto_delete_task(chat_id: int, message_id: int, delay_seconds: int = 240):
    await asyncio.sleep(delay_seconds)
    try:
        await bot.delete_messages(chat_id, message_id)
    except Exception:
        pass

def get_fsub_keyboard(unjoined_channels, file_hash: str):
    buttons = []
    for idx, ch in enumerate(unjoined_channels, start=1):
        display_name = ch.get("title", f"Backup Channel {idx}")
        if len(display_name) > 22:
            display_name = display_name[:19] + "..."

        buttons.append([
            InlineKeyboardButton(
                f"📢 Join {display_name} ➜", 
                url=ch["link"], 
                style=ButtonStyle.PRIMARY
            )
        ])

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

    # ForceSub Verification
    unjoined = await check_fsub(client, user_id)
    if unjoined:
        return await message.reply_text(
            "🔒 **Access Denied!**\n\n"
            "To unlock this file, you must subscribe to our backup channels below.\n\n"
            "1. Tap each channel link below and click **Join**.\n"
            "2. Tap the green **Verify & Refresh Access** button.",
            reply_markup=get_fsub_keyboard(unjoined, file_hash)
        )

    # Deliver file download link
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
            f"⏳ **Security Timer:** This button and link will automatically be deleted in **4 minutes**!",
            reply_markup=keyboard
        )

        asyncio.create_task(auto_delete_task(message.chat.id, sent.id, 240))
        return

    await message.reply_text(
        "👋 **Welcome to the Ultra-Fast File Stream & Link Bot!**\n\n"
        "Send files up to **4 GB** directly to generate high-speed download links.\n"
        "*(Note: File link generation is restricted to the bot owner)*"
    )

@bot.on_callback_query(filters.regex(r"^verify_(.*)"))
async def verify_callback_handler(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    file_hash = query.matches[0].group(1)

    unjoined = await check_fsub(client, user_id)
    if unjoined:
        await query.answer("❌ You haven't joined all channels yet! Please join and retry.", show_alert=True)
        try:
            await query.message.edit_reply_markup(reply_markup=get_fsub_keyboard(unjoined, file_hash))
        except Exception:
            pass
        return

    await query.answer("✅ Verified! Generating download link...", show_alert=False)

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

    # 4 GB (4096 MB) maximum file limit
    if file_size > 4096 * 1024 * 1024:
        size_gb = round(file_size / (1024 * 1024 * 1024), 2)
        return await message.reply_text(
            f"⚠️ **File Exceeds Telegram's 4 GB Maximum ({size_gb} GB)!**\n\n"
            f"Please compress the file under 4.0 GB."
        )

    file_name = getattr(media, "file_name", None)
    if not file_name:
        ext = ".mp4" if message.video else (".mp3" if message.audio else "")
        file_name = f"file_{message.id}{ext}"

    mime_type = getattr(media, "mime_type", "application/octet-stream")

    status_msg = await message.reply_text("🔄 **Forwarding to Unlimited Storage Channel (4GB Mode)...**")

    try:
        # Use forward instead of copy so Telegram preserves >2GB files without failure
        try:
            stored_msg = await message.forward(DB_CHANNEL)
        except Exception:
            stored_msg = await message.copy(DB_CHANNEL)

        file_hash = await save_file(stored_msg.id, file_name, file_size, mime_type)
        bot_username = client.me.username

        deep_link = f"https://t.me/{bot_username}?start=file_{file_hash}"
        direct_web_link = f"{FQDN}/chrome/{file_hash}"

        await status_msg.edit_text(
            f"✅ **4GB File Stored Permanently!**\n\n"
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
    print("✓ Bot client started successfully!")

    if user_bot:
        try:
            await user_bot.start()
            print("✓ User Client connected (4GB high-speed direct pipeline enabled)!")
        except Exception as e:
            print(f"! Warning: User client failed to start: {e}")

    try:
        chat = await bot.get_chat(DB_CHANNEL)
        print(f"✓ Connected to Storage Channel: {chat.title} ({chat.id})")
    except Exception as e:
        print(f"! Storage Channel notice: {e}")

    await refresh_fsub_cache(bot)

    app = init_web_server(bot, user_bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Web server running on port {PORT} with URL {FQDN}")

    await asyncio.Event().wait()

if __name__ == "__main__":
    loop.run_until_complete(main())
