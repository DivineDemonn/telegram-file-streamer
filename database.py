import motor.motor_asyncio
import uuid
from config import MONGO_URI, DATABASE_NAME

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client[DATABASE_NAME]
files_col = db["files"]

async def save_file(message_id: int, file_name: str, file_size: int, mime_type: str) -> str:
    """Stores the Telegram DB channel message ID and returns a unique hash."""
    file_hash = str(uuid.uuid4())[:10]
    await files_col.insert_one({
        "file_hash": file_hash,
        "message_id": message_id,
        "file_name": file_name,
        "file_size": file_size,
        "mime_type": mime_type
    })
    return file_hash

async def get_file(file_hash: str):
    """Retrieves file metadata by hash."""
    return await files_col.find_one({"file_hash": file_hash})
