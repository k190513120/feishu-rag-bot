import json
import lark_oapi as lark
from flask import Flask, request, jsonify, redirect
from lark_oapi.adapter.flask import parse_req, parse_resp

from config import FEISHU_VERIFICATION_TOKEN, FEISHU_ENCRYPT_KEY
from feishu.auth import (
    parse_oauth_state, exchange_code_for_token, store_user_token,
    build_admin_oauth_url, exchange_code_for_admin_token, save_admin_token,
)
from feishu.cards import build_confirm_card
from feishu.event_handler import build_dispatcher
from feishu.message import send_message

app = Flask(__name__)

dispatcher = build_dispatcher(FEISHU_ENCRYPT_KEY, FEISHU_VERIFICATION_TOKEN)


@app.route("/event", methods=["POST"])
def event():
    body = request.get_json(force=True)

    # Handle challenge verification (unencrypted)
    if body.get("type") == "url_verification":
        return jsonify({"challenge": body.get("challenge", "")})

    # Handle challenge verification (encrypted)
    if "encrypt" in body:
        from lark_oapi.core.utils import AESCipher
        try:
            decrypted = json.loads(AESCipher(FEISHU_ENCRYPT_KEY).decrypt_string(body["encrypt"]))
            if decrypted.get("type") == "url_verification":
                return jsonify({"challenge": decrypted.get("challenge", "")})
        except Exception:
            pass  # Not a challenge, fall through to SDK

    raw_req = parse_req()
    raw_resp = dispatcher.do(raw_req)
    return parse_resp(raw_resp)


@app.route("/admin/auth")
def admin_auth():
    """Admin visits this URL to authorize user-identity message sending."""
    return redirect(build_admin_oauth_url())


@app.route("/oauth/callback")
def oauth_callback():
    code = request.args.get("code", "")
    state_raw = request.args.get("state", "")

    if not code or not state_raw:
        return "Missing code or state", 400

    try:
        state = parse_oauth_state(state_raw)
    except Exception:
        return "Invalid state", 400

    # --- Admin authorization flow ---
    if state.get("flow") == "admin":
        token_data = exchange_code_for_admin_token(code)
        if not token_data:
            # Return 200 so load balancer does not retry (code is single-use)
            return "<html><body><h2>授权失败</h2><p>请重新访问 /admin/auth 再试。</p></body></html>"
        save_admin_token(token_data)
        lark.logger.info("Admin user-identity authorization succeeded")
        return (
            "<html><body><h2>管理员授权成功</h2>"
            "<p>后续消息将以用户身份发送。</p></body></html>"
        )

    # --- Original group-join flow ---
    chat_id = state.get("chat_id", "")
    open_chat_id = state.get("open_chat_id", "")
    if not chat_id or not open_chat_id:
        return "Invalid state", 400

    user_token = exchange_code_for_token(code)
    if not user_token:
        # Return 200 so load balancer does not retry (code is single-use)
        return "<html><body><h2>授权失败</h2><p>请重新分享群名片再试。</p></body></html>"

    # Store token for the confirm step
    token_key = f"{open_chat_id}:{chat_id}"
    store_user_token(token_key, user_token)

    # Send confirm card to the p2p chat
    card_content = json.dumps(build_confirm_card(chat_id))
    send_message(open_chat_id, "interactive", card_content)

    lark.logger.info(f"OAuth success, stored token for {token_key}")
    return "<html><body><h2>授权成功</h2><p>请返回飞书，点击「确认」按钮完成入群。</p></body></html>"


@app.route("/")
@app.route("/health")
def health():
    return {"status": "ok"}


def _start_sync():
    """Start the background sync scheduler and run initial sync."""
    from sync.scheduler import run_sync, start_scheduler
    from config import SYNC_INTERVAL_HOURS

    # Run initial sync on startup
    import threading
    threading.Thread(target=run_sync, daemon=True).start()

    # Start periodic scheduler
    start_scheduler(interval_hours=SYNC_INTERVAL_HOURS)


_start_sync()


if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
