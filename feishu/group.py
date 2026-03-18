import lark_oapi as lark
from lark_oapi.api.im.v1 import CreateChatMembersRequest, CreateChatMembersRequestBody

from config import FEISHU_APP_ID
from feishu.client import get_client


def add_bot_to_chat(chat_id: str) -> bool:
    """Add the bot itself to the specified chat. Returns True on success."""
    client = get_client()

    request = CreateChatMembersRequest.builder() \
        .chat_id(chat_id) \
        .member_id_type("app_id") \
        .request_body(
            CreateChatMembersRequestBody.builder()
            .id_list([FEISHU_APP_ID])
            .build()
        ) \
        .build()

    response = client.im.v1.chat_members.create(request)

    if not response.success():
        lark.logger.error(
            f"Failed to add bot to chat {chat_id}: {response.code} {response.msg}"
        )
        return False

    return True
