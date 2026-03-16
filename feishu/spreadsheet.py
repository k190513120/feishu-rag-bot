import json
import lark_oapi as lark
from lark_oapi.core import HttpMethod, AccessTokenType
from lark_oapi.core.model.base_request import BaseRequest
from lark_oapi.api.wiki.v2 import GetNodeSpaceRequest

from feishu.client import get_client
from config import WIKI_TOKEN


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


def list_sheets(spreadsheet_token: str) -> list[dict]:
    """List all sheets in a spreadsheet. Returns list of {sheet_id, title, index}."""
    client = get_client()

    request = BaseRequest.builder() \
        .http_method(HttpMethod.GET) \
        .uri(f"/open-apis/sheets/v3/spreadsheets/:spreadsheetToken/sheets/query") \
        .paths({"spreadsheetToken": spreadsheet_token}) \
        .token_types({AccessTokenType.TENANT}) \
        .build()

    response = client.request(request)

    if not response.success():
        raise RuntimeError(
            f"Failed to list sheets: {response.code} {response.msg}"
        )

    body = json.loads(response.raw.content)
    sheets_data = body.get("data", {}).get("sheets", [])

    sheets = []
    for s in sheets_data:
        sheets.append({
            "sheet_id": s.get("sheet_id", ""),
            "title": s.get("title", ""),
            "index": s.get("index", 0),
        })

    # Sort by index to ensure consistent ordering
    sheets.sort(key=lambda x: x["index"])
    return sheets


def read_sheet(spreadsheet_token: str, sheet_id: str) -> list[dict]:
    """Read all rows from a sheet. Columns: A=模块, B=类型, C=标准问题, D=参考答案."""
    client = get_client()

    range_str = f"{sheet_id}!A:D"

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
    # Skip header row (first row)
    for row in rows[1:]:
        if len(row) < 4:
            continue
        module = str(row[0]).strip() if row[0] else ""
        category = str(row[1]).strip() if row[1] else ""
        question = str(row[2]).strip() if row[2] else ""
        answer = str(row[3]).strip() if row[3] else ""
        if question and answer:
            qa_pairs.append({
                "module": module,
                "category": category,
                "question": question,
                "answer": answer,
            })

    return qa_pairs


def load_qa_pairs() -> list[dict]:
    """Full pipeline: wiki token -> spreadsheet token -> read all sheets -> Q&A rows."""
    spreadsheet_token = resolve_wiki_token(WIKI_TOKEN)
    print(f"Resolved spreadsheet token: {spreadsheet_token}")

    sheets = list_sheets(spreadsheet_token)
    print(f"Found {len(sheets)} sheets: {[s['title'] for s in sheets]}")

    # Skip the first sheet (introduction page)
    data_sheets = sheets[1:]
    if not data_sheets:
        print("No data sheets found (only intro sheet).")
        return []

    all_pairs = []
    for sheet in data_sheets:
        pairs = read_sheet(spreadsheet_token, sheet["sheet_id"])
        print(f"  Sheet '{sheet['title']}': {len(pairs)} Q&A pairs")
        all_pairs.extend(pairs)

    print(f"Loaded {len(all_pairs)} Q&A pairs total")
    return all_pairs
