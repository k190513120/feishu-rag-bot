"""Incremental sync: Feishu spreadsheet -> Pinecone vector database."""
import hashlib
import json
import os
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from feishu.spreadsheet import load_qa_pairs
from embedding.openai_embedder import embed_texts
from vectorstore.pinecone_store import upsert_vectors, delete_vectors

logger = logging.getLogger(__name__)

SYNC_STATE_PATH = os.path.join(os.path.dirname(__file__), "sync_state.json")


def _content_hash(pair: dict) -> str:
    """Compute MD5 hash of a Q&A pair's content."""
    content = f"{pair['module']}|{pair['category']}|{pair['question']}|{pair['answer']}"
    return hashlib.md5(content.encode()).hexdigest()


def _vector_id(pair: dict) -> str:
    """Compute a stable vector ID from question + module (to handle same question in different modules)."""
    key = f"{pair['module']}|{pair['question']}"
    return hashlib.md5(key.encode()).hexdigest()


def _load_sync_state() -> dict[str, str]:
    """Load previous sync state: {vector_id: content_hash}."""
    if not os.path.exists(SYNC_STATE_PATH):
        return {}
    with open(SYNC_STATE_PATH, "r") as f:
        return json.load(f)


def _save_sync_state(state: dict[str, str]):
    """Save sync state to disk."""
    with open(SYNC_STATE_PATH, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def run_sync():
    """Run one incremental sync cycle."""
    logger.info("Starting sync from Feishu spreadsheet...")

    # 1. Read all Q&A pairs from Feishu
    try:
        qa_pairs = load_qa_pairs()
    except Exception as e:
        logger.error(f"Failed to load Q&A pairs from Feishu: {e}")
        return

    if not qa_pairs:
        logger.warning("No Q&A pairs loaded from Feishu. Skipping sync.")
        return

    # 2. Build current state: {vector_id: content_hash}
    current_state = {}
    pairs_by_id = {}
    for pair in qa_pairs:
        vid = _vector_id(pair)
        chash = _content_hash(pair)
        current_state[vid] = chash
        pairs_by_id[vid] = pair

    # 3. Load previous state
    previous_state = _load_sync_state()

    # 4. Compute diff
    current_ids = set(current_state.keys())
    previous_ids = set(previous_state.keys())

    new_ids = current_ids - previous_ids
    removed_ids = previous_ids - current_ids
    # Changed = exists in both but content hash differs
    changed_ids = {
        vid for vid in (current_ids & previous_ids)
        if current_state[vid] != previous_state[vid]
    }

    upsert_ids = new_ids | changed_ids

    logger.info(
        f"Sync diff: {len(new_ids)} new, {len(changed_ids)} changed, "
        f"{len(removed_ids)} removed, {len(current_ids) - len(upsert_ids)} unchanged"
    )

    # 5. Delete removed vectors
    if removed_ids:
        delete_vectors(list(removed_ids))
        logger.info(f"Deleted {len(removed_ids)} vectors")

    # 6. Embed and upsert new/changed vectors
    if upsert_ids:
        pairs_to_upsert = [pairs_by_id[vid] for vid in upsert_ids]
        texts = [f"Q: {p['question']}\nA: {p['answer']}" for p in pairs_to_upsert]
        ids = [vid for vid in upsert_ids]

        # Embed in batches
        batch_size = 50
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            logger.info(f"  Embedding batch {i // batch_size + 1}/{(len(texts) - 1) // batch_size + 1}")
            all_embeddings.extend(embed_texts(batch))

        # Build vectors
        vectors = []
        for vid, pair, embedding in zip(ids, pairs_to_upsert, all_embeddings):
            vectors.append({
                "id": vid,
                "values": embedding,
                "metadata": {
                    "module": pair["module"],
                    "category": pair["category"],
                    "question": pair["question"],
                    "answer": pair["answer"],
                },
            })

        upsert_vectors(vectors)
        logger.info(f"Upserted {len(vectors)} vectors")

    # 7. Save current state
    _save_sync_state(current_state)
    logger.info(f"Sync complete. Total vectors: {len(current_state)}")


def start_scheduler(interval_hours: int = 1):
    """Start the background sync scheduler."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_sync, "interval", hours=interval_hours, id="feishu_sync")
    scheduler.start()
    logger.info(f"Sync scheduler started (interval: {interval_hours}h)")
    return scheduler


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_sync()
