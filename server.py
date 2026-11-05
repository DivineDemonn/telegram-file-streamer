import os
import math
from aiohttp import web
import jinja2
import aiohttp_jinja2
from database import get_file
from config import DB_CHANNEL

routes = web.RouteTableDef()

def format_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

@routes.get("/step1/{file_hash}")
@aiohttp_jinja2.template("step1.html")
async def step_one_handler(request):
    file_hash = request.match_info["file_hash"]
    file_data = await get_file(file_hash)
    if not file_data:
        raise web.HTTPNotFound(text="Link Expired or Invalid File")
    return {
        "file_hash": file_hash,
        "file_name": file_data["file_name"]
    }

@routes.get("/step2/{file_hash}")
@aiohttp_jinja2.template("step2.html")
async def step_two_handler(request):
    file_hash = request.match_info["file_hash"]
    file_data = await get_file(file_hash)
    if not file_data:
        raise web.HTTPNotFound(text="Link Expired or Invalid File")
    return {
        "file_hash": file_hash,
        "file_name": file_data["file_name"],
        "file_size": format_size(file_data["file_size"])
    }

@routes.get("/download/{file_hash}")
async def stream_download_handler(request):
    """Direct high-speed chunk streamer using Telegram Bot client."""
    file_hash = request.match_info["file_hash"]
    file_data = await get_file(file_hash)
    if not file_data:
        raise web.HTTPNotFound(text="File Not Found")

    bot = request.app["bot"]
    msg_id = file_data["message_id"]

    try:
        msg = await bot.get_messages(DB_CHANNEL, msg_id)
        media = getattr(msg, msg.media.value) if msg.media else None
        if not media:
            raise web.HTTPNotFound(text="Underlying Telegram file was deleted")
    except Exception as e:
        raise web.HTTPInternalServerError(text=f"Telegram Error: {str(e)}")

    file_name = file_data.get("file_name", "downloaded_file")
    file_size = file_data.get("file_size", media.file_size)
    mime_type = file_data.get("mime_type", "application/octet-stream")

    response = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": mime_type,
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        }
    )
    await response.prepare(request)

    # High-speed chunk streaming straight into the user's browser
    async for chunk in bot.stream_media(msg):
        await response.write(chunk)

    return response

@routes.get("/")
@routes.get("/health")
async def health_check(request):
    return web.Response(text="Bot & CDN Streamer Online 24/7 🚀")

def init_web_server(bot):
    app = web.Application()
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader("./templates"))
    app["bot"] = bot
    app.add_routes(routes)
    return app
