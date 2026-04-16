import hashlib
import json
import threading
import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1
from lark_oapi.event.callback.model.p2_card_action_trigger import (
    P2CardActionTrigger, P2CardActionTriggerResponse, CallBackToast,
)

from feishu.auth import build_oauth_url, build_admin_oauth_url, get_admin_user_token, pop_user_token
from feishu.cards import build_auth_card, build_user_identity_auth_card
from feishu.chat import is_external_chat
from feishu.group import add_bot_to_chat
from feishu.message import reply_card, reply_text
from feishu.bitable import write_reply_to_bitable
from feishu.history import get_chat_history, format_history_as_context
from bot_api.petal import get_reply

# In-memory dedup set (Feishu retries within 3s)
_seen_message_ids: set[str] = set()
_seen_lock = threading.Lock()
MAX_SEEN = 10000

# Fingerprint set for answers we wrote to Bitable. The Bitable bot reads the
# table and posts our answer back into the chat as a brand-new message with a
# message_id we never see — so message_id dedup cannot catch it. We track the
# answer text instead and skip incoming messages whose content matches.
_sent_answer_fps: set[str] = set()
MAX_ANSWER_FPS = 1000


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _process_message(message_id: str, message_type: str, content_raw: str,
                     chat_id: str) -> None:
    """Process a message in a background thread."""
    try:
        # Handle share_chat messages: start the join-group flow
        if message_type == "share_chat":
            content = json.loads(content_raw)
            target_chat_id = content.get("chat_id", "")
            if target_chat_id:
                oauth_url = build_oauth_url(target_chat_id, chat_id)
                reply_card(message_id, build_auth_card(oauth_url))
            return

        # Only handle text messages; log and ignore everything else silently
        if message_type != "text":
            lark.logger.info(f"Ignoring non-text message_type: {message_type}")
            return

        question = json.loads(content_raw).get("text", "").strip()
        if not question:
            return

        # Skip echoes of answers we wrote to Bitable (external-group path).
        # The Bitable bot relays our answer back into the chat — without this
        # check, that relay would be treated as a new user question.
        with _seen_lock:
            if _fingerprint(question) in _sent_answer_fps:
                lark.logger.info("Skipping bitable echo of own answer")
                return

        lark.logger.info(f"Question from user: {question}")

        session_id = chat_id or "default"

        # Include recent chat history as context so the bot understands the thread
        enriched_question = question
        if chat_id:
            history = get_chat_history(chat_id, exclude_message_id=message_id, limit=5)
            context = format_history_as_context(history)
            if context:
                enriched_question = f"{context}\n\n当前问题：{question}"

        answer = get_reply(enriched_question, session_id)

        if not answer:
            lark.logger.info("External bot returned no answer, skipping reply")
            return

        lark.logger.info(f"Answer: {answer[:100]}...")

        # External group: write to Bitable for the Bitable bot to forward
        # Internal group / p2p: reply directly with user identity
        if chat_id and is_external_chat(chat_id):
            write_reply_to_bitable(answer, chat_id)
            with _seen_lock:
                _sent_answer_fps.add(_fingerprint(answer))
                if len(_sent_answer_fps) > MAX_ANSWER_FPS:
                    _sent_answer_fps.clear()
        else:
            if not get_admin_user_token():
                oauth_url = build_admin_oauth_url()
                reply_card(message_id, build_user_identity_auth_card(oauth_url))
                return
            sent_id = reply_text(message_id, answer)
            # Add our own reply to dedup set so the echo event is ignored
            if sent_id:
                with _seen_lock:
                    _seen_message_ids.add(sent_id)
    except Exception as e:
        lark.logger.error(f"Error processing message {message_id}: {e}", exc_info=True)


def _handle_message(data: P2ImMessageReceiveV1) -> None:
    """Handle im.message.receive_v1 event — dedup then dispatch to background thread."""
    event = data.event
    message = event.message
    message_id = message.message_id

    # Dedup: skip if already processing/processed.
    # Must happen synchronously before returning so Feishu gets 200 immediately
    # and does not retry, which is the root cause of duplicate messages.
    with _seen_lock:
        if message_id in _seen_message_ids:
            lark.logger.info(f"Skipping duplicate message: {message_id}")
            return
        _seen_message_ids.add(message_id)
        if len(_seen_message_ids) > MAX_SEEN:
            _seen_message_ids.clear()

    lark.logger.info(f"Received message_type: {message.message_type}")

    # Dispatch to background thread so this handler returns immediately.
    # Feishu retries when response takes >3s — processing in background prevents retries.
    threading.Thread(
        target=_process_message,
        args=(message.message_id, message.message_type,
              message.content, message.chat_id),
        daemon=True,
    ).start()


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
