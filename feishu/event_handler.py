import json
import threading
import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1
from lark_oapi.event.callback.model.p2_card_action_trigger import (
    P2CardActionTrigger, P2CardActionTriggerResponse, CallBackToast,
)

from feishu.auth import build_oauth_url, build_admin_oauth_url, get_admin_user_token, pop_user_token
from feishu.cards import build_auth_card, build_user_identity_auth_card
from feishu.group import add_bot_to_chat
from feishu.message import reply_card, reply_text
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

    lark.logger.info(f"Received message_type: {message.message_type}")

    # Check user-identity token; prompt authorization if missing
    if not get_admin_user_token():
        oauth_url = build_admin_oauth_url()
        reply_card(message_id, build_user_identity_auth_card(oauth_url))
        return

    # Handle share_chat messages: start the join-group flow
    if message.message_type == "share_chat":
        content = json.loads(message.content)
        chat_id = content.get("chat_id", "")
        if chat_id:
            open_chat_id = message.chat_id
            oauth_url = build_oauth_url(chat_id, open_chat_id)
            reply_card(message_id, build_auth_card(oauth_url))
        return

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


def _handle_card_action(data: P2CardActionTrigger) -> P2CardActionTriggerResponse:
    """Handle interactive card button clicks."""
    event = data.event
    action_value = event.action.value or {}
    action = action_value.get("action", "")
    chat_id = action_value.get("chat_id", "")
    open_chat_id = event.context.open_chat_id

    if action == "confirm_join_group" and chat_id and open_chat_id:
        # Retrieve the user_access_token stored during OAuth callback
        token_key = f"{open_chat_id}:{chat_id}"
        user_token = pop_user_token(token_key)

        resp = P2CardActionTriggerResponse()
        resp.toast = CallBackToast()

        if not user_token:
            resp.toast.type = "error"
            resp.toast.content = "授权已过期，请重新分享群名片"
            return resp

        success = add_bot_to_chat(chat_id, user_token)
        if success:
            resp.toast.type = "success"
            resp.toast.content = "已成功加入群聊"
        else:
            resp.toast.type = "error"
            resp.toast.content = "加入群聊失败，请检查权限后重试"
        return resp

    return P2CardActionTriggerResponse()


def build_dispatcher(encrypt_key: str = "", verification_token: str = "") -> lark.EventDispatcherHandler:
    """Build event dispatcher with all handlers registered."""
    return lark.EventDispatcherHandler.builder(encrypt_key, verification_token) \
        .register_p2_im_message_receive_v1(_handle_message) \
        .register_p2_card_action_trigger(_handle_card_action) \
        .build()
