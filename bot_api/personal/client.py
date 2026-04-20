"""Personal-identity Feishu IM client.

Reverse-engineered client for the Feishu web internal-api gateway. Uses the
caller's session cookie to send messages as a real user, bypassing the open
API limitation that blocks apps from messaging external tenant groups.

This talks to a private undocumented API. Feishu may break it at any time;
callers must treat failures as non-fatal and fall back to another path.
"""
import random
import string
import threading
import time
import uuid
from typing import Optional

import lark_oapi as lark
import requests

from bot_api.personal import proto_pb2 as pb

_IM_GATEWAY = "https://internal-api-lark-api.feishu.cn/im/gateway/"
_CSRF_URL = "https://internal-api-lark-api.feishu.cn/accounts/csrf"
_USER_URL = "https://internal-api-lark-api.feishu.cn/accounts/web/user"

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0")

_ALNUM_62 = string.ascii_letters + string.digits
_BASE36 = string.digits + string.ascii_lowercase


def _request_id() -> str:
    """10-char base36 id, matches Math.random().toString(36).substring(2,12)."""
    return "".join(random.choices(_BASE36, k=10))


def _long_request_id() -> str:
    return str(uuid.uuid4())


def _request_cid() -> str:
    """10-char alnum id used as elementId/cid in protobuf payloads."""
    return "".join(random.choices(_ALNUM_62, k=10))


def _parse_cookie(cookie_str: str) -> dict:
    out = {}
    for part in cookie_str.split("; "):
        if not part or "=" not in part:
            continue
        k, _, v = part.partition("=")
        out[k] = v
    return out


def _gateway_headers(cmd: str) -> dict:
    return {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "content-type": "application/x-protobuf",
        "locale": "zh_CN",
        "origin": "https://open-dev.feishu.cn",
        "referer": "https://open-dev.feishu.cn/",
        "user-agent": _UA,
        "x-appid": "161471",
        "x-command": cmd,
        "x-command-version": "2.7.0",
        "x-lgw-os-type": "1",
        "x-lgw-terminal-type": "2",
        "x-request-id": _request_id(),
        "x-source": "web",
        "x-web-version": "3.9.32",
    }


class PersonalClient:
    """One instance per cookie. Safe for concurrent send_text calls."""

    def __init__(self, cookie_str: str):
        self._session = requests.Session()
        self._session.cookies.update(_parse_cookie(cookie_str))
        self._swp_csrf: Optional[str] = None
        self._lock = threading.Lock()

    def _ensure_csrf(self) -> str:
        if self._swp_csrf:
            return self._swp_csrf
        with self._lock:
            if self._swp_csrf:
                return self._swp_csrf
            hdr = {
                "accept": "application/json, text/plain, */*",
                "content-length": "0",
                "origin": "https://open-dev.feishu.cn",
                "referer": "https://open-dev.feishu.cn/",
                "user-agent": _UA,
                "x-api-version": "1.0.8",
                "x-app-id": "12",
                "x-device-info": "platform=websdk",
                "x-lgw-os-type": "1",
                "x-lgw-terminal-type": "2",
                "x-request-id": _request_id(),
                "x-terminal-type": "2",
            }
            r = self._session.post(_CSRF_URL, headers=hdr, timeout=15)
            if r.status_code != 200:
                raise RuntimeError(
                    f"csrf status={r.status_code} body={r.text[:200]!r}"
                )
            # Use the just-received Set-Cookie, not the session jar (which may
            # carry a stale swp_csrf_token from the initial login cookie string
            # on a different path/domain).
            swp = r.cookies.get("swp_csrf_token", None)
            if not swp:
                raise RuntimeError(f"no swp_csrf_token in response: {dict(r.cookies)}")
            self._swp_csrf = swp
            return swp

    def get_user_info(self) -> dict:
        """Return the parsed JSON body from /accounts/web/user.
        Useful for verifying the cookie is still valid."""
        csrf = self._ensure_csrf()
        hdr = {
            "accept": "application/json, text/plain, */*",
            "origin": "https://open-dev.feishu.cn",
            "referer": "https://open-dev.feishu.cn/",
            "user-agent": _UA,
            "x-api-version": "1.0.8",
            "x-app-id": "12",
            "x-csrf-token": csrf,
            "x-device-info": "platform=websdk",
            "x-lgw-os-type": "1",
            "x-lgw-terminal-type": "2",
            "x-locale": "zh-CN",
            "x-request-id": _long_request_id(),
            "x-terminal-type": "2",
        }
        params = {"app_id": "12", "_t": str(int(time.time() * 1000))}
        r = self._session.get(_USER_URL, headers=hdr, params=params, timeout=15)
        return r.json()

    def search(self, query: str) -> list[dict]:
        """Return list of {id, type (1=user, 3=group), title}."""
        hdr = _gateway_headers("11021")
        packet = pb.Packet()
        packet.payloadType = 1
        packet.cmd = 11021
        packet.cid = hdr["x-request-id"]

        req = pb.UniversalSearchRequest()
        req.header.searchSession = _request_cid()
        req.header.sessionSeqId = 1
        req.header.query = query
        req.header.searchContext.tagName = "SMART_SEARCH"

        for t in (1, 2, 3, 10):  # user, bot, group, chat-with-me
            item = pb.EntityItem()
            item.type = t
            if t == 3:
                item.filter.groupChatFilter.CopyFrom(pb.GroupChatFilter())
            else:
                item.filter.CopyFrom(pb.EntityItem.EntityFilter())
            req.header.searchContext.entityItems.append(item)

        req.header.searchContext.commonFilter.includeOuterTenant = 1
        req.header.searchContext.sourceKey = "messenger"
        req.header.locale = "zh_CN"
        req.header.extraParam.CopyFrom(pb.SearchExtraParam())

        packet.payload = req.SerializeToString()

        r = self._session.post(_IM_GATEWAY, headers=hdr,
                               data=packet.SerializeToString(), timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f"search status={r.status_code} body={r.text[:200]!r}")

        resp_packet = pb.Packet()
        resp_packet.ParseFromString(r.content)
        resp = pb.UniversalSearchResponse()
        resp.ParseFromString(resp_packet.payload)

        return [
            {"id": res.id, "type": res.type, "title": res.titleHighlighted}
            for res in resp.results
        ]

    def send_text(self, internal_chat_id: str, text: str) -> bool:
        """Send a plain-text message to a chat by internal chat id.
        Returns True on HTTP 200, False otherwise (errors are logged)."""
        hdr = _gateway_headers("5")
        cid_1 = _request_cid()
        cid_2 = _request_cid()

        packet = pb.Packet()
        packet.payloadType = 1
        packet.cmd = 5
        packet.cid = hdr["x-request-id"]

        put = pb.PutMessageRequest()
        put.type = 4  # TEXT
        put.chatId = internal_chat_id
        put.cid = cid_1
        put.isNotified = 1
        put.version = 1

        put.content.richText.elementIds.append(cid_2)
        put.content.richText.innerText = text
        put.content.richText.elements.dictionary[cid_2].tag = 1  # TEXT

        prop = pb.TextProperty()
        prop.content = text
        put.content.richText.elements.dictionary[cid_2].property = prop.SerializeToString()

        packet.payload = put.SerializeToString()

        try:
            r = self._session.post(_IM_GATEWAY, headers=hdr,
                                   data=packet.SerializeToString(), timeout=20)
        except Exception as e:
            lark.logger.error(f"PersonalClient.send_text request failed: {type(e).__name__}: {e}")
            return False

        if r.status_code != 200:
            lark.logger.error(
                f"PersonalClient.send_text status={r.status_code} "
                f"body={r.text[:200]!r}"
            )
            # If 401 / session-expired, invalidate so next call re-fetches csrf
            if r.status_code in (401, 403):
                self._swp_csrf = None
            return False
        return True

    def invalidate_csrf(self) -> None:
        """Clear cached swp_csrf_token so the next call re-fetches it."""
        with self._lock:
            self._swp_csrf = None
