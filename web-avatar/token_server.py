"""Token + dispatch server for the web-avatar lane.

Serves:
  GET /            -> web-avatar/index.html (the demo page)
  GET /token?identity=<id>
      -> mints a LiveKit access token for room "sales-avatar" AND creates an
         explicit agent dispatch so the running worker joins that room with
         the Simli avatar attached.

Only needs the LiveKit creds (LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET
in ../.env). Simli keys are only needed by the agent worker, not here.

Run:
    cd web-avatar
    pip install livekit-api        # ships with livekit-agents too
    python token_server.py         # then open http://localhost:8000

In the same terminal (or another), run the agent worker:
    cd voice-agent && python agent.py dev
"""

import json
import logging
import os
import random
import string
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

log = logging.getLogger("token-server")

WEB_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_ROOM = "sales-avatar"          # must NOT start with the SIP room prefix
AGENT_NAME = "sales-voice-agent"   # must match WorkerOptions in agent.py


def load_env():
    """Minimal .env loader (no third-party deps). Existing env wins."""
    path = os.path.join(WEB_DIR, "..", ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def make_livekit_client():
    from livekit import api

    return api.LiveKitAPI(
        url=os.environ["LIVEKIT_URL"],
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )


def mint_token(identity: str) -> str:
    from livekit import api

    return (
        api.AccessToken(os.environ["LIVEKIT_API_KEY"], os.environ["LIVEKIT_API_SECRET"])
        .with_identity(identity)
        .with_name("Website visitor")
        .with_grants(api.VideoGrants(room_join=True, room=WEB_ROOM))
        .to_jwt()
    )


def ensure_dispatch(client) -> None:
    """Ask the agent to join the web room. Best-effort: if the worker isn't
    running (or a dispatch already exists), the token still works and the
    dispatch can be created later from the LiveKit dashboard / `lk` CLI."""
    from livekit.api import CreateAgentDispatchRequest

    try:
        client.agent_dispatch.create_dispatch(
            CreateAgentDispatchRequest(agent_name=AGENT_NAME, room=WEB_ROOM)
        )
        log.info("dispatched %s to room %s", AGENT_NAME, WEB_ROOM)
    except Exception as e:  # noqa: BLE001 - best effort, surfaced in logs
        log.warning("could not create dispatch (worker may not be running): %s", e)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, fmt, *args):  # quieter than default
        log.info(fmt, *args)

    def _json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/token":
            qs = parse_qs(parsed.query)
            identity = qs.get("identity", [None])[0] or (
                "web-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
            )
            try:
                missing = [k for k in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")
                           if not os.environ.get(k)]
                if missing:
                    return self._json(
                        {"error": f"missing env vars: {', '.join(missing)}"}, 500
                    )
                client = make_livekit_client()
                ensure_dispatch(client)
                token = mint_token(identity)
                return self._json(
                    {"token": token, "url": os.environ["LIVEKIT_URL"], "room": WEB_ROOM}
                )
            except Exception as e:  # noqa: BLE001
                log.exception("token minting failed")
                return self._json({"error": str(e)}, 500)
        return super().do_GET()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    load_env()
    port = int(os.environ.get("PORT", "8000"))
    log.info("serving web-avatar demo on http://localhost:%d", port)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
