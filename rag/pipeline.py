import requests
from config import GPT_API_URL, GPT_API_AK
from embedding.openai_embedder import embed_query
from vectorstore.pinecone_store import query as pinecone_query
from rag.prompt_templates import SYSTEM_PROMPT, USER_PROMPT

CHAT_MODEL = "gpt-5.4-2026-03-05"


def retrieve(question: str, top_k: int = 3) -> list[dict]:
    """Embed question and retrieve top_k matching Q&A pairs from Pinecone."""
    vector = embed_query(question)
    return pinecone_query(vector, top_k=top_k)


def build_context(results: list[dict]) -> str:
    """Format retrieved Q&A pairs into context string."""
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f"[{i}] Q: {r['question']}\nA: {r['answer']}")
    return "\n\n".join(parts)


def generate_answer(question: str, top_k: int = 3) -> str:
    """Full RAG pipeline: embed → search → GPT generate."""
    results = retrieve(question, top_k=top_k)

    if not results:
        return "抱歉，我没有找到相关的知识库内容来回答您的问题。"

    context = build_context(results)

    resp = requests.post(
        GPT_API_URL,
        params={"ak": GPT_API_AK},
        json={
            "stream": False,
            "model": CHAT_MODEL,
            "max_tokens": 1024,
            "messages": [
                {"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT.format(context=context)}]},
                {"role": "user", "content": [{"type": "text", "text": USER_PROMPT.format(question=question)}]},
            ],
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    return data["choices"][0]["message"]["content"]
