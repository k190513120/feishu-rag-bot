import lark_oapi as lark
from config import FEISHU_APP_ID, FEISHU_APP_SECRET

_client: lark.Client | None = None
_user_client: lark.Client | None = None


def get_client() -> lark.Client:
    """Bot-identity client (tenant_access_token, auto-managed by SDK)."""
    global _client
    if _client is None:
        _client = lark.Client.builder() \
            .app_id(FEISHU_APP_ID) \
            .app_secret(FEISHU_APP_SECRET) \
            .log_level(lark.LogLevel.INFO) \
            .build()
    return _client


def get_user_client() -> lark.Client:
    """User-identity client (enable_set_token so we can pass user_access_token)."""
    global _user_client
    if _user_client is None:
        _user_client = lark.Client.builder() \
            .app_id(FEISHU_APP_ID) \
            .app_secret(FEISHU_APP_SECRET) \
            .enable_set_token(True) \
            .log_level(lark.LogLevel.INFO) \
            .build()
    return _user_client
