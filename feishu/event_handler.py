import json
import threading
import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from feishu.message import reply_text
from rag.pipeline import generate_answer

# In-memory dedup set (Feishu retries within 3s)
_seen_message_ids: set[str] = set()
_seen_lock = threading.Lock()
MAX_SEEN = 10000


def _handle_message(data: P2ImMessageReceiveV1) -> None:
    """Handle im.message.receive_v1 event."""
    event = data.event
    message = event.message
    message_id = message.message_id

    # Dedup: skip if already processed
    with _seen_lock:
        if message_id in _seen_message_ids:
            lark.logger.info(f"Skipping duplicate message: {message_id}")
            return
        _seen_message_ids.add(message_id)
        # Prevent unbounded growth
        if len(_seen_message_ids) > MAX_SEEN:
            _seen_message_ids.clear()

    # Only handle text messages
    if message.message_type != "text":
        reply_text(message_id, "抱歉，我目前只能处理文本消息。")
        return

    # Extract question text
    content = json.loads(message.content)
    question = content.get("text", "").strip()

    if not question:
        return

    lark.logger.info(f"Question from user: {question}")

    # RAG pipeline
    answer = generate_answer(question)

    lark.logger.info(f"Answer: {answer[:100]}...")

    reply_text(message_id, answer)


def build_dispatcher(encrypt_key: str = "", verification_token: str = "") -> lark.EventDispatcherHandler:
    """Build event dispatcher with all handlers registered."""
    return lark.EventDispatcherHandler.builder(encrypt_key, verification_token) \
        .register_p2_im_message_receive_v1(_handle_message) \
        .build()
