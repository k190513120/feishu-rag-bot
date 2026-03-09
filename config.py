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
GPT_API_URL = _require("GPT_API_URL")
GPT_API_AK = _require("GPT_API_AK")
PINECONE_API_KEY = _require("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "feishu")
FEISHU_VERIFICATION_TOKEN = os.getenv("FEISHU_VERIFICATION_TOKEN", "")
FEISHU_ENCRYPT_KEY = os.getenv("FEISHU_ENCRYPT_KEY", "")
WIKI_TOKEN = _require("WIKI_TOKEN")
SHEET_ID = os.getenv("SHEET_ID", "f20ac6")
