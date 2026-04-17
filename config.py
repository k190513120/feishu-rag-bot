import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required env var: {key}")
    return val


FEISHU_APP_ID = _require("FEISHU_APP_ID")
FEISHU_APP_SECRET = _require("FEISHU_APP_SECRET")
# RAG-related env vars are now optional: answers come from an external bot API.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "feishu")
FEISHU_VERIFICATION_TOKEN = os.getenv("FEISHU_VERIFICATION_TOKEN", "")
FEISHU_ENCRYPT_KEY = os.getenv("FEISHU_ENCRYPT_KEY", "")
WIKI_TOKEN = os.getenv("WIKI_TOKEN", "")
SHEET_ID = os.getenv("SHEET_ID", "f20ac6")
SYNC_INTERVAL_HOURS = int(os.getenv("SYNC_INTERVAL_HOURS", "1"))
# Separate Feishu app for reading spreadsheets (may differ from bot app)
FEISHU_SYNC_APP_ID = os.getenv("FEISHU_SYNC_APP_ID", FEISHU_APP_ID)
FEISHU_SYNC_APP_SECRET = os.getenv("FEISHU_SYNC_APP_SECRET", FEISHU_APP_SECRET)
BASE_URL = os.getenv("BASE_URL", "").rstrip("/")
# External bot API (Petal)
PETAL_ACCESS_KEY_ID = _require("PETAL_ACCESS_KEY_ID")
PETAL_ACCESS_KEY_SECRET = _require("PETAL_ACCESS_KEY_SECRET")
PETAL_BOT_ID = os.getenv("PETAL_BOT_ID", "a7788492-5c7c-4f40-b121-643ce489ed7b")
PETAL_BASE_URL = os.getenv("PETAL_BASE_URL", "https://petal-insight.juzibot.com").rstrip("/")
# Admin operator open_id used to pause/resume bot replies in a given chat.
# Set this after identifying 杜小龙's open_id from the sender log line.
PAUSE_ADMIN_OPEN_ID = os.getenv("PAUSE_ADMIN_OPEN_ID", "")
