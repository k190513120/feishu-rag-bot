import lark_oapi as lark
from lark_oapi.core.model import RequestOption
from lark_oapi.api.im.v1 import CreateChatMembersRequest, CreateChatMembersRequestBody

from config import FEISHU_APP_ID, FEISHU_APP_SECRET


def add_bot_to_chat(chat_id: str, user_access_token: str) -> bool:
    """Add the bot to the specified chat using the user's access token."""
    # Need a client with enable_set_token=True so the SDK actually
    # uses our manually provided user_access_token instead of
    # auto-fetching a tenant_access_token.
    client = lark.Client.builder() \
        .app_id(FEISHU_APP_ID) \
        .app_secret(FEISHU_APP_SECRET) \
        .enable_set_token(True) \
        .log_level(lark.LogLevel.INFO) \
        .build()

    request = CreateChatMembersRequest.builder() \
        .chat_id(chat_id) \
        .member_id_type("app_id") \
        .request_body(
            CreateChatMembersRequestBody.builder()
            .id_list([FEISHU_APP_ID])
            .build()
        ) \
        .build()

    option = RequestOption.builder() \
        .user_access_token(user_access_token) \
        .build()

    response = client.im.v1.chat_members.create(request, option)

    if not response.success():
        lark.logger.error(
            f"Failed to add bot to chat {chat_id}: {response.code} {response.msg}"
        )
        return False

    return True
