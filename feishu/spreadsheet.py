import json
import lark_oapi as lark
from lark_oapi.core import HttpMethod, AccessTokenType
from lark_oapi.core.model.base_request import BaseRequest
from lark_oapi.api.wiki.v2 import GetNodeSpaceRequest

from feishu.client import get_client
from config import WIKI_TOKEN, SHEET_ID


def resolve_wiki_token(wiki_token: str) -> str:
    """Resolve a wiki node token to the underlying spreadsheet obj_token."""
    client = get_client()
    request = GetNodeSpaceRequest.builder().token(wiki_token).build()
    response = client.wiki.v2.space.get_node(request)

    if not response.success():
        raise RuntimeError(
            f"Failed to resolve wiki token: {response.code} {response.msg}"
        )

    return response.data.node.obj_token


def read_sheet(spreadsheet_token: str, sheet_id: str) -> list[dict]:
    """Read all rows from a sheet and return list of {question, answer} dicts."""
    client = get_client()

    range_str = f"{sheet_id}!A:B"

    request = BaseRequest.builder() \
        .http_method(HttpMethod.GET) \
        .uri(f"/open-apis/sheets/v2/spreadsheets/:spreadsheetToken/values/:range") \
        .paths({"spreadsheetToken": spreadsheet_token, "range": range_str}) \
        .token_types({AccessTokenType.TENANT}) \
        .build()

    response = client.request(request)

    if not response.success():
        raise RuntimeError(
            f"Failed to read sheet: {response.code} {response.msg}"
        )

    body = json.loads(response.raw.content)
    rows = body.get("data", {}).get("valueRange", {}).get("values", [])

    qa_pairs = []
    for row in rows:
        if len(row) < 2:
            continue
        q = str(row[0]).strip() if row[0] else ""
        a = str(row[1]).strip() if row[1] else ""
        if q and a:
            qa_pairs.append({"question": q, "answer": a})

    return qa_pairs


def load_qa_pairs() -> list[dict]:
    """Full pipeline: wiki token → spreadsheet token → read Q&A rows."""
    spreadsheet_token = resolve_wiki_token(WIKI_TOKEN)
    print(f"Resolved spreadsheet token: {spreadsheet_token}")
    pairs = read_sheet(spreadsheet_token, SHEET_ID)
    print(f"Loaded {len(pairs)} Q&A pairs")
    return pairs
