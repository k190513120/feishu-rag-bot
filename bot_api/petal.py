import time
import threading
import requests
import lark_oapi as lark

from config import PETAL_ACCESS_KEY_ID, PETAL_ACCESS_KEY_SECRET, PETAL_BOT_ID, PETAL_BASE_URL

_BASE_URL = PETAL_BASE_URL

_token: str | None = None
_token_expires_at: float = 0.0
_token_lock = threading.Lock()


def _fetch_access_token() -> tuple[str, float] | None:
    try:
        resp = requests.post(
            f"{_BASE_URL}/openapi/get-access-token",
            json={
                "accessKeyId": PETAL_ACCESS_KEY_ID,
                "accessKeySecret": PETAL_ACCESS_KEY_SECRET,
            },
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
    except Exception as e:
        lark.logger.error(f"Petal get-access-token request failed: {type(e).__name__}: {e}")
        return None

    try:
        data = resp.json()
    except Exception as e:
        lark.logger.error(
            f"Petal get-access-token non-JSON response: {type(e).__name__}: {e} "
            f"status={resp.status_code} headers={dict(resp.headers)} body={resp.text[:500]!r}"
        )
        return None

    inner = data.get("data") if isinstance(data.get("data"), dict) else data
    token = inner.get("accessToken") or inner.get("access_token")
    expires_in = (
        inner.get("expiresIn")
        or inner.get("expires_in")
        or 3600
    )

    if not token:
        lark.logger.error(f"Petal token response missing accessToken: {data}")
        return None

    return token, time.time() + float(expires_in) - 60


def _get_token() -> str | None:
    global _token, _token_expires_at
    with _token_lock:
        if _token and time.time() < _token_expires_at:
            return _token
        result = _fetch_access_token()
        if not result:
            return None
        _token, _token_expires_at = result
        return _token


def _invalidate_token() -> None:
    global _token, _token_expires_at
    with _token_lock:
        _token = None
        _token_expires_at = 0.0


def get_reply(question: str, session_id: str) -> str | None:
    """Call external bot API for a reply. Returns None on failure or empty response."""
    token = _get_token()
    if not token:
        return None

    def _call(auth_token: str):
        return requests.post(
            f"{_BASE_URL}/openapi/bot/message",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {auth_token}",
            },
            json={
                "botId": PETAL_BOT_ID,
                "sessionId": session_id,
                "message": {"type": "text", "text": question},
                "stream": False,
            },
            timeout=60,
        )

    try:
        resp = _call(token)
        if resp.status_code == 401:
            _invalidate_token()
            token = _get_token()
            if not token:
                return None
            resp = _call(token)
        data = resp.json()
    except Exception as e:
        lark.logger.error(f"Petal bot/message failed: {e}")
        return None

    lark.logger.info(f"Petal reply raw: {str(data)[:300]}")

    inner = data.get("data") if isinstance(data.get("data"), dict) else data
    message = inner.get("message", inner)
    if isinstance(message, dict):
        text = message.get("text") or message.get("content")
    elif isinstance(message, str):
        text = message
    else:
        text = None

    if not text:
        lark.logger.warning(f"Petal reply contains no text: {data}")
        return None

    return text
