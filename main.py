import json
from flask import Flask, request, jsonify
from lark_oapi.adapter.flask import parse_req, parse_resp

from config import FEISHU_VERIFICATION_TOKEN, FEISHU_ENCRYPT_KEY
from feishu.event_handler import build_dispatcher

app = Flask(__name__)

dispatcher = build_dispatcher(FEISHU_ENCRYPT_KEY, FEISHU_VERIFICATION_TOKEN)


@app.route("/event", methods=["POST"])
def event():
    # Handle challenge verification directly (before SDK processing)
    body = request.get_json(force=True)
    if body.get("type") == "url_verification":
        return jsonify({"challenge": body.get("challenge", "")})

    raw_req = parse_req()
    raw_resp = dispatcher.do(raw_req)
    return parse_resp(raw_resp)


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
