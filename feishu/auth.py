import json
import os
import base64
import time
import threading
from urllib.parse import urlencode

import requests
import lark_oapi as lark

from config import FEISHU_APP_ID, FEISHU_APP_SECRET, BASE_URL

# Temporary in-memory store: key -> user_access_token (for group-join flow)
_token_store: dict[str, str] = {}
_token_lock = threading.Lock()

# Persistent admin token file (user-identity messaging)
_ADMIN_TOKEN_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), ".admin_token.json"
)
_admin_token_lock = threading.Lock()


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


# --------------- Admin user-identity token management ---------------

def build_admin_oauth_url() -> str:
    """Build OAuth URL for admin to authorize user-identity message sending."""
    state = base64.urlsafe_b64encode(
        json.dumps({"flow": "admin"}).encode()
    ).decode()
    params = urlencode({
        "app_id": FEISHU_APP_ID,
        "redirect_uri": f"{BASE_URL}/oauth/callback",
        "scope": "im:message im:message.send_as_user",
        "state": state,
    })
    return f"https://open.feishu.cn/open-apis/authen/v1/authorize?{params}"


def exchange_code_for_admin_token(code: str) -> dict | None:
    """Exchange OAuth code for admin token data (includes refresh_token)."""
    token_resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
    )
    app_token = token_resp.json().get("app_access_token")
    if not app_token:
        lark.logger.error("Failed to get app_access_token for admin auth")
        return None

    resp = requests.post(
        "https://open.feishu.cn/open-apis/authen/v1/oidc/access_token",
        headers={"Authorization": f"Bearer {app_token}"},
        json={"grant_type": "authorization_code", "code": code},
    )
    data = resp.json()
    lark.logger.info(f"Admin token exchange response: {data}")
    if data.get("code") != 0:
        lark.logger.error(f"Admin OAuth token exchange failed: {data}")
        return None
    return data["data"]


def save_admin_token(token_data: dict):
    """Persist admin token to local file."""
    expires_in = token_data.get("expires_in", 7200)
    data = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token", ""),
        "expires_at": time.time() + expires_in - 60,  # 60s safety buffer
    }
    with _admin_token_lock:
        with open(_ADMIN_TOKEN_FILE, "w") as f:
            json.dump(data, f)


def _load_admin_token() -> dict | None:
    if not os.path.exists(_ADMIN_TOKEN_FILE):
        return None
    with open(_ADMIN_TOKEN_FILE) as f:
        return json.load(f)


def _refresh_admin_token(refresh_token: str) -> dict | None:
    """Use refresh_token to obtain a new user_access_token."""
    token_resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET},
    )
    app_token = token_resp.json().get("app_access_token")
    if not app_token:
        return None

    resp = requests.post(
        "https://open.feishu.cn/open-apis/authen/v1/oidc/refresh_access_token",
        headers={"Authorization": f"Bearer {app_token}"},
        json={"grant_type": "refresh_token", "refresh_token": refresh_token},
    )
    data = resp.json()
    if data.get("code") != 0:
        lark.logger.error(f"Admin token refresh failed: {data}")
        return None
    return data["data"]


def get_admin_user_token() -> str | None:
    """Return a valid admin user_access_token, refreshing automatically if expired."""
    with _admin_token_lock:
        token_data = _load_admin_token()
    if not token_data:
        return None

    if time.time() < token_data["expires_at"]:
        return token_data["access_token"]

    # Token expired — try refresh
    refresh_token = token_data.get("refresh_token", "")
    if not refresh_token:
        lark.logger.info("Admin token expired and no refresh_token, need re-authorization")
        return None

    lark.logger.info("Admin user_access_token expired, refreshing...")
    refreshed = _refresh_admin_token(refresh_token)
    if not refreshed:
        lark.logger.error("Failed to refresh admin token, need re-authorization")
        return None
    save_admin_token(refreshed)
    return refreshed["access_token"]
