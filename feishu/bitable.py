import json
import os
from typing import Optional

import lark_oapi as lark
from lark_oapi.core import HttpMethod, AccessTokenType
from lark_oapi.core.model.base_request import BaseRequest

from feishu.client import get_client

BITABLE_APP_TOKEN = "PnRtbGmTpaVXwDsWBWPcPaEpnwh"
BITABLE_TABLE_ID = "tblgCeMmHrA7PYQr"

# Optional companion tables. If the env var is unset the feature is disabled
# and send_as_person() will silently no-op.
BITABLE_CONFIG_TABLE_ID = os.getenv("BITABLE_CONFIG_TABLE_ID", "")
BITABLE_CHAT_MAP_TABLE_ID = os.getenv("BITABLE_CHAT_MAP_TABLE_ID", "")


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


def _search_records(table_id: str, field_name: str, value: str) -> list[dict]:
    """Search records where field_name exactly equals value. Returns list of
    {record_id, fields} dicts. Empty on error or no match."""
    client = get_client()
    body = {
        "filter": {
            "conjunction": "and",
            "conditions": [{
                "field_name": field_name,
                "operator": "is",
                "value": [value],
            }],
        },
        "automatic_fields": False,
    }
    request = BaseRequest.builder() \
        .http_method(HttpMethod.POST) \
        .uri("/open-apis/bitable/v1/apps/:app_token/tables/:table_id/records/search") \
        .paths({"app_token": BITABLE_APP_TOKEN, "table_id": table_id}) \
        .body(body) \
        .token_types({AccessTokenType.TENANT}) \
        .build()
    response = client.request(request)
    if not response.success():
        lark.logger.error(
            f"Bitable search failed table={table_id} field={field_name}: "
            f"{response.code} {response.msg}"
        )
        return []
    try:
        payload = json.loads(response.raw.content.decode("utf-8"))
    except Exception as e:
        lark.logger.error(f"Bitable search: non-JSON response: {e}")
        return []
    return payload.get("data", {}).get("items", []) or []


def _field_text(field_value) -> str:
    """Bitable text fields come back as [{type:text,text:str}] sometimes and as
    plain str other times — normalize to str."""
    if isinstance(field_value, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in field_value
        )
    if field_value is None:
        return ""
    return str(field_value)


def get_config_value(key: str) -> Optional[str]:
    """Look up a row in the bot_config table by key column, return `value`.
    Schema expected: key (text), value (长文本)."""
    if not BITABLE_CONFIG_TABLE_ID:
        return None
    items = _search_records(BITABLE_CONFIG_TABLE_ID, "key", key)
    if not items:
        return None
    return _field_text(items[0].get("fields", {}).get("value", "")) or None


def find_chat_mapping(open_chat_id: str) -> Optional[dict]:
    """Look up a chat mapping by open_chat_id. Returns
    {record_id, internal_chat_id, chat_name} or None.
    Schema expected: open_chat_id, chat_name, internal_chat_id, source."""
    if not BITABLE_CHAT_MAP_TABLE_ID:
        return None
    items = _search_records(BITABLE_CHAT_MAP_TABLE_ID, "open_chat_id", open_chat_id)
    if not items:
        return None
    first = items[0]
    fields = first.get("fields", {})
    return {
        "record_id": first.get("record_id", ""),
        "internal_chat_id": _field_text(fields.get("internal_chat_id", "")),
        "chat_name": _field_text(fields.get("chat_name", "")),
    }


def save_chat_mapping(open_chat_id: str, chat_name: str,
                      internal_chat_id: str, source: str = "auto") -> bool:
    """Insert a new chat_mapping row. No upsert: caller should check
    find_chat_mapping first."""
    if not BITABLE_CHAT_MAP_TABLE_ID:
        return False
    client = get_client()
    body = {
        "fields": {
            "open_chat_id": open_chat_id,
            "chat_name": chat_name,
            "internal_chat_id": internal_chat_id,
            "source": source,
        }
    }
    request = BaseRequest.builder() \
        .http_method(HttpMethod.POST) \
        .uri("/open-apis/bitable/v1/apps/:app_token/tables/:table_id/records") \
        .paths({"app_token": BITABLE_APP_TOKEN, "table_id": BITABLE_CHAT_MAP_TABLE_ID}) \
        .body(body) \
        .token_types({AccessTokenType.TENANT}) \
        .build()
    response = client.request(request)
    if not response.success():
        lark.logger.error(
            f"save_chat_mapping failed open_chat_id={open_chat_id}: "
            f"{response.code} {response.msg}"
        )
        return False
    return True
