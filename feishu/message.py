import json
import lark_oapi as lark
from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody

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
