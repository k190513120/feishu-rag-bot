"""High-level send-as-person orchestration.

Responsibilities:
  1. Load the session cookie from the Bitable bot_config table, cached in
     memory with a TTL so we aren't hammering Bitable on every message.
  2. Resolve open_chat_id -> internal_chat_id via the Bitable chat_mapping
     table, auto-populating it via the Feishu Open API (chat name) plus a
     personal-identity search when a row is missing.
  3. Send text via the reverse-engineered PersonalClient.

All failures are logged and return False; the caller keeps its Bitable-write
fallback path so the user always receives *some* answer even if the
personal-identity channel is down.
"""
import re
import threading
import time
from typing import Optional

import lark_oapi as lark
from lark_oapi.api.im.v1 import GetChatRequest

from bot_api.personal import PersonalClient
from feishu.bitable import (
    find_chat_mapping, get_config_value, save_chat_mapping,
)
from feishu.client import get_client

_COOKIE_KEY = "personal_cookie"
_COOKIE_CACHE_TTL_SECONDS = 600  # 10 minutes

_HTML_HIGHLIGHT = re.compile(r"</?h>")

_cookie_lock = threading.Lock()
_cookie_value: Optional[str] = None
_cookie_expires_at: float = 0.0

_client_lock = threading.Lock()
_client_instance: Optional[PersonalClient] = None
_client_cookie_sig: Optional[str] = None

_mapping_cache: dict[str, str] = {}
_mapping_lock = threading.Lock()


def _get_cookie() -> Optional[str]:
    global _cookie_value, _cookie_expires_at
    with _cookie_lock:
        if _cookie_value and time.time() < _cookie_expires_at:
            return _cookie_value
        val = get_config_value(_COOKIE_KEY)
        if not val:
            return None
        _cookie_value = val
        _cookie_expires_at = time.time() + _COOKIE_CACHE_TTL_SECONDS
        return val


def _get_client() -> Optional[PersonalClient]:
    global _client_instance, _client_cookie_sig
    cookie = _get_cookie()
    if not cookie:
        return None
    sig = str(hash(cookie))
    with _client_lock:
        if _client_instance is None or _client_cookie_sig != sig:
            _client_instance = PersonalClient(cookie)
            _client_cookie_sig = sig
        return _client_instance


def invalidate_cookie_cache() -> None:
    """Force the next send_as_person to re-read cookie from Bitable."""
    global _cookie_value, _cookie_expires_at, _client_instance, _client_cookie_sig
    with _cookie_lock:
        _cookie_value = None
        _cookie_expires_at = 0.0
    with _client_lock:
        _client_instance = None
        _client_cookie_sig = None


def _fetch_chat_name(open_chat_id: str) -> Optional[str]:
    try:
        resp = get_client().im.v1.chat.get(
            GetChatRequest.builder().chat_id(open_chat_id).build()
        )
        if not resp.success():
            lark.logger.error(
                f"GetChat({open_chat_id}) failed: {resp.code} {resp.msg}"
            )
            return None
        return resp.data.name or None
    except Exception as e:
        lark.logger.error(
            f"GetChat({open_chat_id}) exception: {type(e).__name__}: {e}"
        )
        return None


def _search_internal_id(chat_name: str) -> Optional[str]:
    pc = _get_client()
    if not pc:
        return None
    try:
        results = pc.search(chat_name)
    except Exception as e:
        lark.logger.error(
            f"Personal search({chat_name!r}) exception: {type(e).__name__}: {e}"
        )
        return None
    # Prefer exact-name group match over fuzzy first-group fallback.
    groups = [
        (r["id"], _HTML_HIGHLIGHT.sub("", r["title"]))
        for r in results if r["type"] == 3
    ]
    for gid, clean_title in groups:
        if clean_title == chat_name:
            return gid
    if groups:
        lark.logger.warning(
            f"No exact-name match for {chat_name!r}; falling back to first "
            f"group: {groups[0][1]!r}"
        )
        return groups[0][0]
    return None


def _resolve_internal_chat_id(open_chat_id: str) -> Optional[str]:
    """Look up open_chat_id -> internal_chat_id. Auto-resolves and saves on
    first encounter. Returns None when mapping exists but is empty (operator
    must fill it in Bitable)."""
    with _mapping_lock:
        cached = _mapping_cache.get(open_chat_id)
    if cached:
        return cached

    row = find_chat_mapping(open_chat_id)
    if row:
        internal_id = row.get("internal_chat_id")
        if internal_id:
            with _mapping_lock:
                _mapping_cache[open_chat_id] = internal_id
            return internal_id
        lark.logger.info(
            f"chat_mapping row for {open_chat_id} has empty internal_chat_id; "
            f"waiting for manual fill"
        )
        return None

    name = _fetch_chat_name(open_chat_id)
    if not name:
        return None
    internal_id = _search_internal_id(name)
    if internal_id:
        save_chat_mapping(open_chat_id, name, internal_id, source="auto")
        with _mapping_lock:
            _mapping_cache[open_chat_id] = internal_id
        lark.logger.info(
            f"Auto-mapped {open_chat_id} -> {internal_id} ({name!r})"
        )
        return internal_id
    save_chat_mapping(open_chat_id, name, "", source="auto")
    lark.logger.warning(
        f"Auto-map failed for {open_chat_id} ({name!r}); row saved with "
        f"empty internal_chat_id for manual fill"
    )
    return None


def send_as_person(open_chat_id: str, text: str) -> bool:
    """Send `text` to the chat identified by `open_chat_id` using the personal
    identity stored in Bitable. Non-fatal: returns False on any failure."""
    if not open_chat_id or not text:
        return False

    pc = _get_client()
    if not pc:
        lark.logger.warning(
            "send_as_person: no personal_cookie in bot_config table, skipping"
        )
        return False

    internal_id = _resolve_internal_chat_id(open_chat_id)
    if not internal_id:
        return False

    ok = pc.send_text(internal_id, text)
    if not ok:
        invalidate_cookie_cache()
    return ok
