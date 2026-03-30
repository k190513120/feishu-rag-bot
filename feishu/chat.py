import lark_oapi as lark
from lark_oapi.api.im.v1 import GetChatRequest

from feishu.client import get_client

# Cache chat_id -> is_external to avoid repeated API calls
_chat_external_cache: dict[str, bool] = {}


def is_external_chat(chat_id: str) -> bool:
    """Return True if chat_id is an external group. Result is cached."""
    if chat_id in _chat_external_cache:
        return _chat_external_cache[chat_id]

    client = get_client()
    request = GetChatRequest.builder().chat_id(chat_id).build()
    response = client.im.v1.chat.get(request)

    if not response.success():
        lark.logger.error(f"GetChat failed for {chat_id}: {response.code} {response.msg}")
        return False

    external = response.data.external or False
    _chat_external_cache[chat_id] = external
    lark.logger.info(f"Chat {chat_id} is_external={external}")
    return external
