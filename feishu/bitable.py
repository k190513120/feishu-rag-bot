import lark_oapi as lark
from lark_oapi.core import HttpMethod, AccessTokenType
from lark_oapi.core.model.base_request import BaseRequest

from feishu.client import get_client

BITABLE_APP_TOKEN = "PnRtbGmTpaVXwDsWBWPcPaEpnwh"
BITABLE_TABLE_ID = "tblgCeMmHrA7PYQr"


def write_reply_to_bitable(reply_content: str, chat_id: str) -> None:
    """Write AI reply and source group chat to Bitable."""
    client = get_client()

    body = {
        "fields": {
            "消息内容": reply_content,
            "飞书外部群": [{"id": chat_id}],
        }
    }

    request = BaseRequest.builder() \
        .http_method(HttpMethod.POST) \
        .uri("/open-apis/bitable/v1/apps/:app_token/tables/:table_id/records") \
        .paths({"app_token": BITABLE_APP_TOKEN, "table_id": BITABLE_TABLE_ID}) \
        .body(body) \
        .token_types({AccessTokenType.TENANT}) \
        .build()

    response = client.request(request)
    if not response.success():
        lark.logger.error(f"Write to bitable failed: {response.code} {response.msg}")
    else:
        lark.logger.info(f"Written to bitable, record_id: {response.raw.content[:100]}")
