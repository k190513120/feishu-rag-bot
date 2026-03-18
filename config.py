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
OPENROUTER_API_KEY = _require("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
PINECONE_API_KEY = _require("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "feishu")
FEISHU_VERIFICATION_TOKEN = os.getenv("FEISHU_VERIFICATION_TOKEN", "")
FEISHU_ENCRYPT_KEY = os.getenv("FEISHU_ENCRYPT_KEY", "")
WIKI_TOKEN = _require("WIKI_TOKEN")
SHEET_ID = os.getenv("SHEET_ID", "f20ac6")
SYNC_INTERVAL_HOURS = int(os.getenv("SYNC_INTERVAL_HOURS", "1"))
# Separate Feishu app for reading spreadsheets (may differ from bot app)
FEISHU_SYNC_APP_ID = os.getenv("FEISHU_SYNC_APP_ID", FEISHU_APP_ID)
FEISHU_SYNC_APP_SECRET = os.getenv("FEISHU_SYNC_APP_SECRET", FEISHU_APP_SECRET)
BASE_URL = os.getenv("BASE_URL", "").rstrip("/")
