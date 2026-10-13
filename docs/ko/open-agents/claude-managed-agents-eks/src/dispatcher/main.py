# Dispatcher for Anthropic Managed Agents self-hosted sandboxes on EKS.
#
# One small, long-lived process. It long-polls the Anthropic work queue, and for
# each work item it creates a SandboxClaim (binding a pre-warmed pod from the
# SandboxWarmPool in well under a second), then POSTs {session_id, work_id} to the
# bound pod. The pod then execs `ant beta:worker run`.
#
# The dispatcher holds the environment key (to poll + stop work items) but runs no
# untrusted code itself. The blast radius of any single sandbox is one session.

import argparse
import json
import logging
import os
import time
import urllib.request

import anthropic
from k8s_agent_sandbox import SandboxClient
from k8s_agent_sandbox.models import SandboxInClusterConnectionConfig
from kubernetes import client as k8s
from kubernetes import config as k8s_config

log = logging.getLogger("dispatcher")

# Agent Sandbox CRD group/version. The v1.0.x OSS controller serves v1beta1.
# Older (v0.4.x/v0.5.x) controllers served v1alpha1 — set SANDBOX_API_VERSION
# accordingly if you run one. The k8s-agent-sandbox SDK also pins the version
# internally, so match the SDK release to your controller release.
SBX_GROUP = os.environ.get("SANDBOX_API_GROUP", "extensions.agents.x-k8s.io")
SBX_VERSION = os.environ.get("SANDBOX_API_VERSION", "v1beta1")

DISPATCH_COUNT_LABEL = "anthropic.com/dispatch-count"


def parse_args():
    """Parse CLI flags, with defaults from the matching env vars."""
    p = argparse.ArgumentParser()
    p.add_argument("--environment-id", default=os.environ.get("ANTHROPIC_ENVIRONMENT_ID"))
    p.add_argument("--namespace", default=os.environ.get("SANDBOX_NAMESPACE", "claude-agents"))
    p.add_argument("--template", default=os.environ.get("SANDBOX_TEMPLATE", "claude-agent-worker"))
    p.add_argument("--warmpool", default=os.environ.get("SANDBOX_WARMPOOL", "claude-agent-worker"))
    p.add_argument("--dispatch-port", type=int, default=int(os.environ.get("DISPATCH_PORT", "8080")))
    p.add_argument("--ready-timeout", type=int,
                   default=int(os.environ.get("SANDBOX_READY_TIMEOUT", "120")))
    p.add_argument("--block-ms", type=int, default=int(os.environ.get("POLL_BLOCK_MS", "900")))
    p.add_argument("--idle-backoff", type=float,
                   default=float(os.environ.get("POLL_IDLE_BACKOFF_SECONDS", "1.0")))
    p.add_argument("--reclaim-older-than-ms", type=int,
                   default=int(os.environ.get("RECLAIM_OLDER_THAN_MS", "120000")))
    p.add_argument("--max-redispatch", type=int,
                   default=int(os.environ.get("MAX_REDISPATCH", "3")))
    return p.parse_args()


def reap_stale_claims(co: k8s.CustomObjectsApi, namespace: str, session_id: str) -> int:
    """Delete any prior SandboxClaim for this session; return its highest dispatch count."""
    resp = co.list_namespaced_custom_object(
        SBX_GROUP, SBX_VERSION, namespace, "sandboxclaims",
        label_selector=f"anthropic.com/session-id={session_id}",
    )
    prev = 0
    for item in resp.get("items", []):
        meta = item["metadata"]
        prev = max(prev, int((meta.get("labels") or {}).get(DISPATCH_COUNT_LABEL, "0")))
        log.info("session=%s reaping stale claim=%s (dispatch #%d)", session_id, meta["name"], prev)
        co.delete_namespaced_custom_object(
            SBX_GROUP, SBX_VERSION, namespace, "sandboxclaims", meta["name"]
        )
    return prev


def post_with_retry(url: str, body: bytes, *, attempts: int = 5, timeout: int = 5) -> None:
    """POST `body` to `url` with exponential backoff; raise the last error on failure."""
    last_err = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(
                url, data=body, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=timeout):
                return
        except OSError as e:
            last_err = e
            time.sleep(0.5 * (2 ** i))
    raise last_err


def dispatch(ant: anthropic.Anthropic, sbx: SandboxClient, co: k8s.CustomObjectsApi, args,
             *, session_id: str, work_id: str) -> None:
    """Claim a warm pod for one work item and POST the session binding to it."""
    prev = reap_stale_claims(co, args.namespace, session_id)
    attempt = prev + 1
    if attempt > args.max_redispatch:
        # Stop zombie work items: a deleted session can keep getting re-offered.
        log.warning("session=%s exceeded max-redispatch=%d; stopping work item",
                    session_id, args.max_redispatch)
        ant.beta.environments.work.stop(environment_id=args.environment_id, work_id=work_id)
        return

    sb = sbx.create_sandbox(
        namespace=args.namespace,
        warmpool=args.warmpool,          # the warmpool already references the SandboxTemplate
        labels={
            "anthropic.com/session-id": session_id,
            DISPATCH_COUNT_LABEL: str(attempt),
        },
        sandbox_ready_timeout=args.ready_timeout,
    )
    try:
        # The per-claim headless Service DNS record is too new to resolve on the
        # first call, so bind to the pod IP directly.
        pod_name = sb.get_pod_name()
        pod = sb.k8s_helper.core_v1_api.read_namespaced_pod(pod_name, sb.namespace)
        host = pod.status.pod_ip
        if not host:
            raise RuntimeError(f"pod {pod_name} bound but has no podIP")
        log.info("session=%s work=%s -> pod=%s host=%s", session_id, work_id, pod_name, host)
        post_with_retry(
            f"http://{host}:{args.dispatch_port}/",
            json.dumps({"session_id": session_id, "work_id": work_id}).encode(),
        )
    except Exception:
        sb.terminate()
        raise


def main():
    """Poll the Anthropic work queue forever and dispatch each item to a sandbox."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", force=True)
    args = parse_args()
    if not args.environment_id:
        raise SystemExit("ANTHROPIC_ENVIRONMENT_ID is not set")

    k8s_config.load_incluster_config()
    # The environment key is a bearer token -> auth_token=, not api_key=.
    ant = anthropic.Anthropic(auth_token=os.environ["ANTHROPIC_ENVIRONMENT_KEY"])
    sbx = SandboxClient(
        connection_config=SandboxInClusterConnectionConfig(
            use_pod_ip=True, server_port=args.dispatch_port
        )
    )
    co = k8s.CustomObjectsApi()
    log.info("polling environment=%s template=%s ns=%s", args.environment_id, args.template, args.namespace)

    while True:
        try:
            item = ant.beta.environments.work.poll(
                args.environment_id,
                block_ms=args.block_ms,
                reclaim_older_than_ms=args.reclaim_older_than_ms,
            )
        except anthropic.APIError as e:
            log.warning("poll error: %s; backing off", e)
            time.sleep(5)
            continue

        if item is None:
            # An empty queue returns immediately; back off to avoid a busy loop.
            time.sleep(args.idle_backoff)
            continue

        session_id, work_id = item.data.id, item.id
        try:
            dispatch(ant, sbx, co, args, session_id=session_id, work_id=work_id)
        except Exception:
            log.exception("dispatch failed session=%s work=%s; will be reclaimed", session_id, work_id)


if __name__ == "__main__":
    main()
