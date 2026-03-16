from pinecone import Pinecone, ServerlessSpec
from config import PINECONE_API_KEY, PINECONE_INDEX

_pc = Pinecone(api_key=PINECONE_API_KEY)
DIMENSION = 1536


def _get_index():
    existing = [idx.name for idx in _pc.list_indexes()]
    if PINECONE_INDEX not in existing:
        _pc.create_index(
            name=PINECONE_INDEX,
            dimension=DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
    return _pc.Index(PINECONE_INDEX)


def upsert_vectors(vectors: list[dict]):
    """Upsert vectors to Pinecone. Each dict has: id, values, metadata."""
    index = _get_index()
    # Upsert in batches of 100
    batch_size = 100
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        index.upsert(vectors=[(v["id"], v["values"], v["metadata"]) for v in batch])
    print(f"Upserted {len(vectors)} vectors to Pinecone")


def delete_vectors(ids: list[str]):
    """Delete vectors by IDs from Pinecone."""
    if not ids:
        return
    index = _get_index()
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        index.delete(ids=batch)
    print(f"Deleted {len(ids)} vectors from Pinecone")


def list_all_ids() -> set[str]:
    """List all vector IDs in the Pinecone index."""
    index = _get_index()
    all_ids = set()

    # Use list() with pagination to fetch all IDs
    for id_list in index.list():
        all_ids.update(id_list)

    return all_ids


def query(vector: list[float], top_k: int = 3) -> list[dict]:
    """Query Pinecone and return top_k results with metadata."""
    index = _get_index()
    results = index.query(vector=vector, top_k=top_k, include_metadata=True)
    return [
        {
            "score": match.score,
            "question": match.metadata.get("question", ""),
            "answer": match.metadata.get("answer", ""),
        }
        for match in results.matches
    ]
