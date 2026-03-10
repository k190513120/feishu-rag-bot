from openai import OpenAI
from config import OPENAI_API_KEY

_client = OpenAI(api_key=OPENAI_API_KEY)
MODEL = "text-embedding-3-small"


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Returns list of 1536-dim vectors."""
    response = _client.embeddings.create(input=texts, model=MODEL)
    return [item.embedding for item in response.data]


def embed_query(text: str) -> list[float]:
    """Embed a single query text."""
    return embed_texts([text])[0]
