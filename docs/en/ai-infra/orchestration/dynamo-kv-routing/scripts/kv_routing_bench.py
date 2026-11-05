#!/usr/bin/env python3
# SPDX-License-Identifier: MIT-0
"""Multi-tenant shared-prefix benchmark for KV-aware routing (stdlib only).

Workload: N "tenants", each with its own long system prompt (think: per-customer
RAG context, agent instructions, or a long chat history). Tenants take turns
(--pattern rounds): every tenant sends one request per round, in a new random
order each round, with a short, unique question appended. Every request after a
tenant's first one could reuse that tenant's cached prefix, IF it lands on the
GPU that already holds it.

  - Round-robin spreads each tenant over both workers. Once all tenants'
    prefixes no longer fit in ONE GPU's KV cache, they evict each other. A
    tenant comes back only after the other tenants have had their turn, by
    which time its prefix has usually been evicted (an LRU cache's worst case).
  - KV-aware routing sends each tenant back to the worker that holds its
    blocks, so each GPU only has to hold about half of the tenants.

Defaults (8 tenants x ~5,500 tokens = ~44K tokens of prefixes) are sized for
the lab's 32K-token-per-GPU cache: too big for one GPU, comfortable for two.

Each run generates new random prefixes from --seed, so a second run never
benefits from cache left behind by the first. Use a different seed per run.

Pass --worker-metrics with the workers' metrics URLs to also print the
server-side vLLM prefix-cache hit rate for exactly this run.

Run it inside the cluster, next to the frontends (see the lab guide). Through
`kubectl port-forward` from a laptop, every request first uploads a ~5,500-token
prompt over the API-server tunnel, which adds hundreds of milliseconds of
network time to every TTFT and hides the difference between the routers:
  kubectl run kv-bench -n dynamo-system --rm -i --restart=Never \
    --image=public.ecr.aws/docker/library/python:3.12-slim -- \
    python3 - --url http://qwen3-8b-kv-frontend:8000 --label kv-router --seed 2 \
    < kv_routing_bench.py
"""

import argparse
import concurrent.futures as cf
import json
import random
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
import re

WORDS = (
    "account active address agent alert amount analysis api application archive audit "
    "backup balance batch billing branch budget buffer cache capacity catalog channel "
    "checkout cluster compliance config contract cost customer dashboard database "
    "deadline delivery deployment discount document domain encryption endpoint "
    "escalation event export feature filter forecast gateway governance incident "
    "inventory invoice latency ledger license limit migration monitor network order "
    "outage partner payment pipeline policy pricing priority procurement product "
    "quota region release renewal report request resource revenue review risk "
    "rollback schedule schema security segment service shipment storage subscription "
    "supplier support tenant ticket timeline token traffic usage vendor version "
    "volume warehouse workflow workload zone quarterly regional update approved pending"
).split()


def build_prefix(rng: random.Random, tenant: int, words: int) -> str:
    """A long, tenant-specific system prompt (deterministic for a seed)."""
    body = []
    for s in range(words // 12):
        sentence = " ".join(rng.choice(WORDS) for _ in range(11))
        body.append(f"{sentence.capitalize()} (ref T{tenant}-{s}).")
    return (
        f"You are the support assistant for tenant {tenant}. Use only the knowledge "
        f"base below to answer.\n\nKNOWLEDGE BASE (tenant {tenant}):\n" + " ".join(body)
    )


def one_request(url, model, system, question, max_tokens, timeout):
    """Stream one chat completion; return (ttft_s, total_s, prompt_tokens, ok)."""
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": question}],
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "stream": True,
        "stream_options": {"include_usage": True},
        # Qwen3: skip the <think> block so outputs stay short and comparable.
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    ttft, prompt_tokens = None, None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                if ttft is None and any(
                    (c.get("delta") or {}).get("content") for c in chunk.get("choices", [])
                ):
                    ttft = time.perf_counter() - t0
                usage = chunk.get("usage")
                if usage:
                    prompt_tokens = usage.get("prompt_tokens")
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        print(f"  request failed: {e}", file=sys.stderr)
        return None, None, None, False
    total = time.perf_counter() - t0
    return (ttft if ttft is not None else total), total, prompt_tokens, True


def scrape_prefix_cache(urls, timeout=5):
    """Sum vLLM prefix-cache counters per worker metrics URL -> {url: (hits, queries)}."""
    out = {}
    for u in urls:
        try:
            with urllib.request.urlopen(u.rstrip("/") + "/metrics", timeout=timeout) as r:
                text = r.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            print(f"  metrics scrape failed for {u}: {e}", file=sys.stderr)
            continue
        vals = {}
        for name in ("hits", "queries"):
            m = re.findall(rf"^vllm:prefix_cache_{name}_total(?:{{[^}}]*}})? ([0-9.eE+-]+)$", text, re.M)
            vals[name] = sum(float(x) for x in m)
        out[u] = (vals["hits"], vals["queries"])
    return out


def build_order(rng, tenants, requests, pattern, gap):
    """Tenant index for each request.

    random: tenants drawn in random order (balanced counts). Hot tenants recur
            quickly, which is friendly to an LRU cache even under round-robin.
    rounds: every tenant once per round, in a fresh shuffle each round, like N
            chat users taking turns. A tenant comes back only after ~N others,
            the access pattern where an LRU cache that is too small for all N
            gets almost no hits. `gap` keeps the same tenant from repeating
            within `gap` requests across a round boundary (no self-overlap
            while it is still in flight).
    """
    if pattern == "random":
        order = [i % tenants for i in range(requests)]
        rng.shuffle(order)
        return order
    order = []
    while len(order) < requests:
        rnd = list(range(tenants))
        for _ in range(1000):
            rng.shuffle(rnd)
            if not set(rnd[:gap]) & set(order[-gap:]):
                break
        order.extend(rnd)
    return order[:requests]


def pct(values, p):
    if not values:
        return float("nan")
    s = sorted(values)
    k = max(0, min(len(s) - 1, round(p / 100 * (len(s) - 1))))
    return s[k]


def summarize(name, values):
    if not values:
        return f"  {name:<24} n=0"
    return (
        f"  {name:<24} n={len(values):<4} mean={statistics.mean(values) * 1000:7.0f} ms  "
        f"p50={pct(values, 50) * 1000:7.0f} ms  p90={pct(values, 90) * 1000:7.0f} ms  "
        f"p99={pct(values, 99) * 1000:7.0f} ms"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://localhost:8000", help="Dynamo frontend base URL")
    ap.add_argument("--model", default="Qwen/Qwen3-8B")
    ap.add_argument("--label", default="run", help="name printed in the summary")
    ap.add_argument("--seed", type=int, default=1, help="new seed per run = fresh prefixes")
    # 3300 words ~= 5,500 Qwen3 tokens (~1.7 tokens/word: the "(ref T3-12)" tags
    # are token-heavy). 8 tenants x 5,500 = ~44K tokens: more than one GPU's
    # 32K-token lab cache, comfortably less than both together. Few, long
    # prefixes make a miss (full prefill, ~450 ms) far costlier than a hit.
    ap.add_argument("--tenants", type=int, default=8)
    ap.add_argument("--prefix-words", type=int, default=3300,
                    help="words per tenant system prompt (~1.7 Qwen3 tokens/word)")
    ap.add_argument("--requests", type=int, default=160)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--max-tokens", type=int, default=32)
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--pattern", choices=("rounds", "random"), default="rounds",
                    help="tenant arrival order (see build_order)")
    ap.add_argument("--worker-metrics", default="",
                    help="comma-separated worker metrics URLs (http://<pod-ip>:9090) to "
                         "report the server-side prefix-cache hit rate for this run")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    prefixes = [build_prefix(rng, t, args.prefix_words) for t in range(args.tenants)]
    order = build_order(rng, args.tenants, args.requests, args.pattern, min(args.concurrency, args.tenants // 2))
    # Short, unique question per request (the non-shared suffix).
    questions = [
        f"Question {i}: list three items from section T{t}-{rng.randrange(1000)} and explain why."
        for i, t in enumerate(order)
    ]

    print(f"[{args.label}] {args.url}  tenants={args.tenants}  prefix~{args.prefix_words} words  "
          f"requests={args.requests}  concurrency={args.concurrency}  pattern={args.pattern}  seed={args.seed}")
    metric_urls = [u.strip() for u in args.worker_metrics.split(",") if u.strip()]
    before = scrape_prefix_cache(metric_urls)

    seen, lock = set(), threading.Lock()
    first_touch, repeat, totals, prompt_toks, failures = [], [], [], [], 0

    def task(i_tenant):
        i, tenant = i_tenant
        with lock:
            is_first = tenant not in seen
            seen.add(tenant)
        return is_first, one_request(
            args.url, args.model, prefixes[tenant], questions[i], args.max_tokens, args.timeout
        )

    t_start = time.perf_counter()
    with cf.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for n, (is_first, (ttft, total, ptoks, ok)) in enumerate(pool.map(task, enumerate(order)), 1):
            if not ok:
                failures += 1
                continue
            (first_touch if is_first else repeat).append(ttft)
            totals.append(total)
            if ptoks:
                prompt_toks.append(ptoks)
            if n % 20 == 0:
                print(f"  {n}/{len(order)} done")
    wall = time.perf_counter() - t_start

    print(f"\n[{args.label}] results  (wall {wall:.1f}s, {len(totals) / wall:.2f} req/s, failures={failures})")
    if prompt_toks:
        print(f"  prompt length          ~{statistics.mean(prompt_toks):.0f} tokens/request")
    print(summarize("TTFT first-touch", first_touch))
    print(summarize("TTFT repeat (cacheable)", repeat))
    print(summarize("end-to-end latency", totals))
    if metric_urls:
        after = scrape_prefix_cache(metric_urls)
        th = tq = 0.0
        for u in metric_urls:
            if u in before and u in after:
                dh, dq = after[u][0] - before[u][0], after[u][1] - before[u][1]
                th, tq = th + dh, tq + dq
                print(f"  prefix-cache hit {u:<28} {100 * dh / dq if dq else 0:5.1f}%  ({dq:,.0f} prompt tokens)")
        if tq:
            print(f"  prefix-cache hit (all workers)      {100 * th / tq:5.1f}%  "
                  f"(ceiling ~{100 * (1 - args.tenants / args.requests):.0f}%: first touches always miss)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
