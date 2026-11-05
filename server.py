import os
import math
from aiohttp import web
import jinja2
import aiohttp_jinja2
from database import get_file
from config import DB_CHANNEL, FQDN

routes = web.RouteTableDef()

def format_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

@routes.get("/chrome/{file_hash}")
async def auto_chrome_redirect(request):
    file_hash = request.match_info["file_hash"]
    clean_domain = FQDN.replace("https://", "").replace("http://", "").rstrip("/")
    target_path = f"{clean_domain}/step1/{file_hash}"
    full_target_url = f"{FQDN}/step1/{file_hash}"

    html_intent = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Opening Google Chrome...</title>
  <script>
    const hostPath = "{target_path}";
    const fullUrl = "{full_target_url}";

    if (/Android/i.test(navigator.userAgent)) {{
      window.location.href = "intent://" + hostPath + "#Intent;scheme=https;package=com.android.chrome;end";
      setTimeout(() => {{
        window.location.href = fullUrl;
      }}, 1000);
    }} else {{
      window.location.href = fullUrl;
    }}
  </script>
  <style>
    body {{
      background: #090d16;
      color: #e2e8f0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
      margin: 0;
      text-align: center;
      padding: 20px;
    }}
    .box {{
      background: rgba(22, 27, 46, 0.9);
      padding: 30px;
      border-radius: 16px;
      border: 1px solid rgba(0, 230, 118, 0.3);
      max-width: 420px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }}
    a {{
      color: #00e676;
      text-decoration: none;
      font-weight: bold;
    }}
  </style>
</head>
<body>
  <div class="box">
    <h2 style="color: #00e676; margin-bottom: 12px;">⚡ Launching Chrome...</h2>
    <p style="color: #94a3b8; font-size: 14px;">Switching to Google Chrome for super-fast multi-threaded download speed.</p>
    <p style="margin-top: 18px;"><a href="{full_target_url}">Click here if Chrome didn't open automatically</a></p>
  </div>
</body>
</html>"""
    return web.Response(text=html_intent, content_type="text/html")

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
    file_hash = request.match_info["file_hash"]
    file_data = await get_file(file_hash)
    if not file_data:
        raise web.HTTPNotFound(text="File Not Found")

    # Select user_bot if configured for full 4GB speed, otherwise fallback to bot
    stream_client = request.app.get("user_bot") or request.app.get("bot")
    msg_id = file_data["message_id"]

    try:
        msg = await stream_client.get_messages(DB_CHANNEL, msg_id)
        media = getattr(msg, msg.media.value) if msg.media else None
        if not media:
            raise web.HTTPNotFound(text="File not found in storage channel")
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

    # Stream chunks directly from Telegram DC to client browser
    async for chunk in stream_client.stream_media(msg):
        await response.write(chunk)

    return response

@routes.get("/")
@routes.get("/health")
async def health_check(request):
    return web.Response(text="Bot & CDN Streamer Online 24/7 🚀")

def init_web_server(bot, user_bot=None):
    app = web.Application()
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader("./templates"))
    app["bot"] = bot
    app["user_bot"] = user_bot
    app.add_routes(routes)
    return app
