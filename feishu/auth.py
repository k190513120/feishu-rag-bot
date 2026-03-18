import json
import base64
import threading
from urllib.parse import urlencode

import requests
import lark_oapi as lark

from config import FEISHU_APP_ID, FEISHU_APP_SECRET, BASE_URL

# Temporary in-memory store: key -> user_access_token
_token_store: dict[str, str] = {}
_token_lock = threading.Lock()


def build_oauth_url(chat_id: str, open_chat_id: str) -> str:
    """Build Feishu OAuth authorization URL."""
    state = base64.urlsafe_b64encode(
        json.dumps({"chat_id": chat_id, "open_chat_id": open_chat_id}).encode()
    ).decode()
    params = urlencode({
        "app_id": FEISHU_APP_ID,
        "redirect_uri": f"{BASE_URL}/oauth/callback",
        "scope": "im:chat im:chat.members:write_only",
        "state": state,
    })
    return f"https://open.feishu.cn/open-apis/authen/v1/authorize?{params}"


def parse_oauth_state(state: str) -> dict:
    """Decode the state parameter from OAuth callback."""
    return json.loads(base64.urlsafe_b64decode(state))


def exchange_code_for_token(code: str) -> str | None:
    """Exchange OAuth authorization code for user_access_token."""
    # Get app_access_token
    token_resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
    )
    app_token = token_resp.json().get("app_access_token")
    if not app_token:
        lark.logger.error("Failed to get app_access_token")
        return None

    # Exchange code for user token
    resp = requests.post(
        "https://open.feishu.cn/open-apis/authen/v1/oidc/access_token",
        headers={"Authorization": f"Bearer {app_token}"},
        json={"grant_type": "authorization_code", "code": code},
    )
    data = resp.json()
    if data.get("code") != 0:
        lark.logger.error(f"OAuth token exchange failed: {data}")
        return None

    return data["data"]["access_token"]


def store_user_token(key: str, token: str):
    with _token_lock:
        _token_store[key] = token


def pop_user_token(key: str) -> str | None:
    with _token_lock:
        return _token_store.pop(key, None)
