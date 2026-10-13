#!/usr/bin/env python3
# Warm-pool worker entrypoint for Anthropic Managed Agents self-hosted sandboxes.
#
# A warm pod does not know which session it will serve until the dispatcher binds
# a SandboxClaim and POSTs {session_id, work_id} to this listener. We block on that
# POST, point /mnt/session/outputs at a per-session subdirectory of the mounted
# PVC, then exec `ant beta:worker run`, which acks the work item, downloads the
# agent's skills + memory stores, runs each tool call locally, and streams results
# back to api.anthropic.com.
#
# The only Anthropic credential in this pod is ANTHROPIC_ENVIRONMENT_KEY (a bearer
# token scoped to one environment's work queue). The org API key never reaches here.

import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("DISPATCH_PORT", "8080"))
MAX_IDLE = os.environ.get("ANT_MAX_IDLE", "60s")
OUTPUTS_MOUNT = os.environ.get("OUTPUTS_MOUNT", "/mnt/outputs")
SESSION_OUTPUTS = os.environ.get("SESSION_OUTPUTS", "/mnt/session/outputs")

# Anthropic session/work ids are opaque url-safe strings; validate before use.
ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")


class Handler(BaseHTTPRequestHandler):
    """Accept exactly one validated {session_id, work_id} POST from the dispatcher."""

    def do_POST(self):  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length))
            session_id, work_id = body["session_id"], body["work_id"]
            if not (ID_RE.match(session_id) and ID_RE.match(work_id)):
                raise ValueError("invalid id")
        except Exception:
            self.send_response(400)
            self.end_headers()
            return
        self.send_response(202)
        self.end_headers()
        self.server.dispatch = {"session_id": session_id, "work_id": work_id}

    def log_message(self, *_):
        """Suppress the stdlib per-request access log (we emit structured logs instead)."""
        pass


def main():
    """Block until dispatched, point outputs at the PVC, then exec `ant beta:worker run`."""
    httpd = HTTPServer(("0.0.0.0", PORT), Handler)
    httpd.dispatch = None
    while httpd.dispatch is None:
        httpd.handle_request()

    payload = httpd.dispatch
    env = os.environ.copy()
    env["ANTHROPIC_SESSION_ID"] = payload["session_id"]
    env["ANTHROPIC_WORK_ID"] = payload["work_id"]

    # Late-bind /mnt/session/outputs to a per-session prefix on the mounted PVC so
    # deliverables survive the short-lived pod. Falls back to a local dir if no PVC.
    if os.path.isdir(OUTPUTS_MOUNT):
        session_dir = os.path.join(OUTPUTS_MOUNT, payload["session_id"])
        os.makedirs(session_dir, exist_ok=True)
        os.makedirs(os.path.dirname(SESSION_OUTPUTS), exist_ok=True)
        if os.path.lexists(SESSION_OUTPUTS):
            os.remove(SESSION_OUTPUTS)
        os.symlink(session_dir, SESSION_OUTPUTS)
    else:
        os.makedirs(SESSION_OUTPUTS, exist_ok=True)

    argv = [
        "ant", "beta:worker", "run",
        "--workdir", "/workspace",
        "--max-idle", MAX_IDLE,
        "--log-format", "json",
    ]
    # ant beta:worker run requires the environment id (via flag or
    # $ANTHROPIC_ENVIRONMENT_ID). session_id / work_id come from the dispatch POST.
    env_id = os.environ.get("ANTHROPIC_ENVIRONMENT_ID")
    if env_id:
        argv += ["--environment-id", env_id]
    argv += [
        "--session-id", payload["session_id"],
        "--work-id", payload["work_id"],
    ]
    print(
        json.dumps({"event": "exec", "argv": argv, "session_id": payload["session_id"]}),
        file=sys.stderr,
    )
    os.execvpe(argv[0], argv, env)


if __name__ == "__main__":
    main()
