from openai import OpenAI
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL

_client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
MODEL = "openai/text-embedding-3-small"


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Returns list of 1536-dim vectors."""
    response = _client.embeddings.create(input=texts, model=MODEL)
    return [item.embedding for item in response.data]


def embed_query(text: str) -> list[float]:
    """Embed a single query text."""
    return embed_texts([text])[0]
