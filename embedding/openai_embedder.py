import requests
from config import GPT_API_URL, GPT_API_AK

MODEL = "text-embedding-3-small"


def _call_embedding_api(input_data) -> dict:
    resp = requests.post(
        GPT_API_URL,
        params={"ak": GPT_API_AK},
        json={
            "stream": False,
            "model": MODEL,
            "encoding_format": "float",
            "dimensions": 1536,
            "input": input_data,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Returns list of 1536-dim vectors."""
    result = _call_embedding_api(texts)
    data = sorted(result["data"], key=lambda x: x["index"])
    return [item["embedding"] for item in data]


def embed_query(text: str) -> list[float]:
    """Embed a single query text."""
    result = _call_embedding_api(text)
    return result["data"][0]["embedding"]
