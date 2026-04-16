import json
import lark_oapi as lark
from lark_oapi.api.im.v1 import ListMessageRequest

from feishu.client import get_client


def get_chat_history(chat_id: str, exclude_message_id: str = "",
                     limit: int = 10) -> list[dict]:
    """Fetch recent text messages from a chat in chronological order.

    Returns list of {"sender_type": "user|bot", "text": "..."}.
    """
    client = get_client()
    request = ListMessageRequest.builder() \
        .container_id_type("chat") \
        .container_id(chat_id) \
        .page_size(min(limit + 10, 50)) \
        .sort_type("ByCreateTimeDesc") \
        .build()

    response = client.im.v1.message.list(request)
    if not response.success():
        lark.logger.error(
            f"List messages failed for {chat_id}: {response.code} {response.msg}"
        )
        return []

    messages: list[dict] = []
    for item in (response.data.items or []):
        if item.message_id == exclude_message_id:
            continue
        if item.msg_type != "text":
            continue
        try:
            raw = item.body.content if item.body else ""
            text = json.loads(raw).get("text", "").strip() if raw else ""
        except Exception:
            continue
        if not text:
            continue
        sender_type = "bot" if (item.sender and item.sender.sender_type == "app") else "user"
        messages.append({"sender_type": sender_type, "text": text})
        if len(messages) >= limit:
            break

    messages.reverse()
    return messages


def format_history_as_context(history: list[dict]) -> str:
    """Format chat history into a context string for the bot API."""
    if not history:
        return ""
    lines = ["以下是本群最近的聊天记录："]
    for m in history:
        role = "助手" if m["sender_type"] == "bot" else "用户"
        lines.append(f"[{role}] {m['text']}")
    return "\n".join(lines)
