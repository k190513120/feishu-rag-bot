import json
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)
from lark_oapi.core.model import RequestOption

from feishu.client import get_client, get_user_client
from feishu.auth import get_admin_user_token


def _user_option() -> RequestOption | None:
    """Build RequestOption with admin user_access_token, or None if unavailable."""
    token = get_admin_user_token()
    if not token:
        return None
    return RequestOption.builder().user_access_token(token).build()


def reply_text(message_id: str, text: str):
    """Reply to a Feishu message with plain text (threaded reply)."""
    content = json.dumps({"text": text})

    request = ReplyMessageRequest.builder() \
        .message_id(message_id) \
        .request_body(
            ReplyMessageRequestBody.builder()
            .content(content)
            .msg_type("text")
            .build()
        ) \
        .build()

    option = _user_option()
    if option:
        response = get_user_client().im.v1.message.reply(request, option)
    else:
        response = get_client().im.v1.message.reply(request)

    if not response.success():
        lark.logger.error(
            f"Reply failed: {response.code} {response.msg}"
        )


def reply_card(message_id: str, card: dict):
    """Reply to a Feishu message with an interactive card."""
    content = json.dumps(card)

    request = ReplyMessageRequest.builder() \
        .message_id(message_id) \
        .request_body(
            ReplyMessageRequestBody.builder()
            .content(content)
            .msg_type("interactive")
            .build()
        ) \
        .build()

    option = _user_option()
    if option:
        response = get_user_client().im.v1.message.reply(request, option)
    else:
        response = get_client().im.v1.message.reply(request)

    if not response.success():
        lark.logger.error(
            f"Reply card failed: {response.code} {response.msg}"
        )


def send_message(chat_id: str, msg_type: str, content: str):
    """Send a message to a chat directly (not as a reply)."""
    request = CreateMessageRequest.builder() \
        .receive_id_type("chat_id") \
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type(msg_type)
            .content(content)
            .build()
        ) \
        .build()

    option = _user_option()
    if option:
        response = get_user_client().im.v1.message.create(request, option)
    else:
        response = get_client().im.v1.message.create(request)

    if not response.success():
        lark.logger.error(
            f"Send message failed: {response.code} {response.msg}"
        )
