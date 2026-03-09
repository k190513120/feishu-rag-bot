import lark_oapi as lark
from config import FEISHU_APP_ID, FEISHU_APP_SECRET

_client: lark.Client | None = None


def get_client() -> lark.Client:
    global _client
    if _client is None:
        _client = lark.Client.builder() \
            .app_id(FEISHU_APP_ID) \
            .app_secret(FEISHU_APP_SECRET) \
            .log_level(lark.LogLevel.INFO) \
            .build()
    return _client
