from openai import OpenAI
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL
from embedding.openai_embedder import embed_query
from vectorstore.pinecone_store import query as pinecone_query
from rag.prompt_templates import SYSTEM_PROMPT, USER_PROMPT

_client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)


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


SIMILARITY_THRESHOLD = 0.75


def generate_answer(question: str, top_k: int = 3) -> str | None:
    """Full RAG pipeline: embed → search → GPT-4o generate.
    Returns None when no result clears SIMILARITY_THRESHOLD."""
    results = retrieve(question, top_k=top_k)

    relevant = [r for r in results if r.get("score", 0) >= SIMILARITY_THRESHOLD]
    if not relevant:
        return None

    context = build_context(relevant)

    response = _client.chat.completions.create(
        model="openai/gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
            {"role": "user", "content": USER_PROMPT.format(question=question)},
        ],
        temperature=0.3,
        max_tokens=1024,
    )

    return response.choices[0].message.content
