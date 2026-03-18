import json
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)

from feishu.client import get_client


def reply_text(message_id: str, text: str):
    """Reply to a Feishu message with plain text (threaded reply)."""
    client = get_client()

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

    response = client.im.v1.message.reply(request)

    if not response.success():
        lark.logger.error(
            f"Reply failed: {response.code} {response.msg}"
        )


def reply_card(message_id: str, card: dict):
    """Reply to a Feishu message with an interactive card."""
    client = get_client()

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

    response = client.im.v1.message.reply(request)

    if not response.success():
        lark.logger.error(
            f"Reply card failed: {response.code} {response.msg}"
        )


def send_message(chat_id: str, msg_type: str, content: str):
    """Send a message to a chat directly (not as a reply)."""
    client = get_client()

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

    response = client.im.v1.message.create(request)

    if not response.success():
        lark.logger.error(
            f"Send message failed: {response.code} {response.msg}"
        )
