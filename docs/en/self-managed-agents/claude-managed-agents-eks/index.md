---
title: Claude Managed Agents on EKS (Self-Hosted Sandboxes)
description: Run the execution side of Anthropic Managed Agents inside your own EKS cluster — a dispatcher pulls tool calls from Anthropic's work queue and binds each one to a pre-warmed, gVisor-isolated sandbox pod
---

# Claude Managed Agents on Amazon EKS — Self-Hosted Sandboxes

[Anthropic Managed Agents](https://platform.claude.com/docs/en/managed-agents) is a hosted agent loop: Claude, conversation state, and a per-environment work queue all run on Anthropic's control plane. With [self-hosted sandboxes](https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes), the orchestration stays on Anthropic's side but **tool and code execution moves into infrastructure you control** — inside your VPC, behind your egress policy, under your audit controls. The agent's files, processes, and network traffic stay in your environment.

This guide deploys that execution layer on **Amazon EKS** using the [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) project. It adapts Anthropic's reference architecture (originally published for [GKE Agent Sandbox](https://agent-sandbox.sigs.k8s.io/docs/use-cases/anthropic-managed-agents/)) to EKS with Karpenter, gVisor isolation, EKS-native storage, and Kubernetes network policies.

!!! warning "Preview software"
    Anthropic self-hosted sandboxes and the Agent Sandbox project are both early-stage. Their APIs may change without notice. Use this as a starting point for your own deployment, not a production-hardened configuration.

## When to self-host

Self-hosting is the right choice when the agent needs to:

- Operate on data that cannot leave your network boundary
- Reach internal services that are not publicly routable
- Run under your organization's own compliance and audit controls

If none of these apply, Anthropic's default managed cloud sandboxes are simpler.

## Why a warm pool, not N long-lived workers

Anthropic's simplest reference is "run N copies of `ant beta:worker poll`." That works, but every replica is a long-lived process that holds the environment key and keeps an open egress to `api.anthropic.com`, and every session that lands on a replica shares the same `/workspace`.

The Agent Sandbox primitives split the responsibilities:

- **One small dispatcher** polls the queue. It holds no untrusted code — it only binds claims.
- **Each work item gets a `SandboxClaim`**, which binds a pre-warmed pod from the `SandboxWarmPool` in well under a second, so a new session never waits on an image pull.
- **One session per pod.** The pod runs the worker for exactly one session and is torn down when the session ends. The blast radius of any single sandbox is one session.
- **The warm pool refills** behind it, keeping the next session fast.

## Why Standard EKS + Karpenter (not Auto Mode)

gVisor requires installing the `runsc` containerd shim on nodes at boot. EKS Auto Mode doesn't allow custom AMIs or user-data, making that impossible. Standard EKS with Karpenter gives you custom node configuration (AL2023 user-data installs gVisor at boot), dedicated tainted NodePools so only sandbox workloads land on isolation-capable nodes, and fast autoscaling.

## Architecture

```
┌───────────────────────────┐          ┌──────────────────────────────────────────────┐
│  Anthropic control plane   │          │  Your Amazon EKS cluster · Agent Sandbox      │
│                            │          │                                                │
│   ┌──────────────┐         │  poll    │   ┌────────────┐                               │
│   │  work queue  │◀────────┼──────────┼───│ dispatcher │  (holds env key, no          │
│   └──────┬───────┘         │          │   └─────┬──────┘   untrusted code)             │
│          │ session_id      │          │         │ SandboxClaim                         │
│          │                 │          │         ▼                                      │
│          │                 │          │   ┌──────────────┐   binds   ┌──────────────┐  │
│          │                 │          │   │SandboxWarmPool│─────────▶│ worker pod   │  │
│          │                 │  ant     │   └──────────────┘           │ (gVisor)     │  │
│   ┌──────▼───────┐         │  worker  │                              │ ant worker   │  │
│   │  Claude loop │◀────────┼──run─────┼──────────────────────────────│ run          │  │
│   └──────────────┘  tool   │  results │                              └──────┬───────┘  │
│                     calls  │          │                                     │          │
└───────────────────────────┘          │                       /mnt/session/outputs     │
                                        │                              ▼                 │
                                        │                        ┌───────────┐           │
                                        │                        │ gp3 PVC   │           │
                                        │                        └───────────┘           │
                                        └──────────────────────────────────────────────┘
```

Two Anthropic credentials are involved, and keeping them separate is the core of the security model:

| Credential | Prefix | Scope | Where it lives |
|------------|--------|-------|----------------|
| **Environment key** | `sk-ant-oat01-...` | Ack work + post tool results for **one** environment | Dispatcher and worker pods only |
| **Org API key** | `sk-ant-api03-...` | Full API access | **Your machine only** — creates agents/sessions; never in the cluster |

## How it works, end to end

1. You create a session that targets your self-hosted environment. Anthropic enqueues it as a work item.
2. The **dispatcher** long-polls the work queue, claims the item, and creates a `SandboxClaim` that binds a ready pod from the warm pool.
3. **Late binding:** the pod is already running before the dispatcher knows which session it will serve, so the session ID can't be a container env var. The worker image runs a tiny HTTP listener and blocks until the dispatcher POSTs `{session_id, work_id}` to it.
4. The worker then execs `ant beta:worker run`. `ant` acks the work item, downloads the agent's skills and memory stores, runs each tool call locally, and streams results back to `api.anthropic.com`.
5. When the session goes idle the worker exits, the controller deletes the sandbox, and the warm pool spins up a fresh replacement.

---

## Prerequisites

- An **Amazon EKS Standard cluster** (1.30+) with **Karpenter**, the **EBS CSI driver** add-on, and a CNI that enforces `NetworkPolicy` (the VPC CNI with network policy enabled, or Cilium).
- The **Agent Sandbox controller** installed in the cluster (serves the `agents.x-k8s.io` and `extensions.agents.x-k8s.io` CRDs). See [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox). The manifests here use `v1alpha1`; set `SANDBOX_API_VERSION=v1beta1` on the dispatcher if your controller serves v1beta1.
- `kubectl`, `kustomize`, `docker buildx`, and the AWS CLI on your PATH.
- An **Anthropic account with Managed Agents access**, your **org API key**, and the **Anthropic CLI** (`ant`) installed locally:

    ```bash
    ANT_VERSION=1.9.1
    ARCH=$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')
    case "$(uname -s)" in
      Darwin) curl -fsSL "https://github.com/anthropics/anthropic-cli/releases/download/v${ANT_VERSION}/ant_${ANT_VERSION}_macos_${ARCH}.zip" -o /tmp/ant.zip && sudo unzip -o /tmp/ant.zip ant -d /usr/local/bin && rm /tmp/ant.zip ;;
      Linux)  curl -fsSL "https://github.com/anthropics/anthropic-cli/releases/download/v${ANT_VERSION}/ant_${ANT_VERSION}_linux_${ARCH}.tar.gz" | sudo tar -xz -C /usr/local/bin ant ;;
    esac
    ant --version
    ```

    If the download 404s, check the [Anthropic CLI releases](https://github.com/anthropics/anthropic-cli/releases) for a newer version.

Set shared shell variables used throughout:

```bash
export CLUSTER_NAME=my-eks-cluster
export AWS_REGION=us-west-2
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR=${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
```

---

## Module 1 — Create a self-hosted environment on Anthropic

An environment is the work queue that links Anthropic's agent loop to your cluster. Create one of type **Self-hosted** in the [Anthropic Console](https://platform.claude.com/) (**Environments → New → Self-hosted**), or via the API:

```bash
export ANTHROPIC_API_KEY=sk-ant-api03-YOUR_ORG_KEY   # org key, this command only

curl https://api.anthropic.com/v1/environments \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: managed-agents-2026-04-01" \
  -H "content-type: application/json" \
  -d '{"name":"eks-agent-sandbox","config":{"type":"self_hosted"}}'
```

Collect two values:

- **Environment ID** (`env_01...`) — the `id` in the API response, or in the Console URL of the environment detail page.
- **Environment key** (`sk-ant-oat01-...`) — open the environment in the Console and click **Generate environment key**. You can only generate it in the Console.

```bash
export ANTHROPIC_ENVIRONMENT_ID=env_01...
export ANTHROPIC_ENVIRONMENT_KEY=sk-ant-oat01-...
```

**Checkpoint:** you have both an `env_...` ID and an `sk-ant-oat01-...` key.

---

## Module 2 — Build and push the images

Two images: the **worker** (ships `ant` + the dispatch listener) and the **dispatcher** (polls the queue, binds claims). Both target `linux/arm64` for Graviton.

```bash
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR"

for repo in claude-agent-worker claude-agent-dispatcher; do
  aws ecr describe-repositories --repository-names "$repo" --region "$AWS_REGION" >/dev/null 2>&1 \
    || aws ecr create-repository --repository-name "$repo" --region "$AWS_REGION" >/dev/null
done

docker buildx build --platform linux/arm64 \
  -t "$ECR/claude-agent-worker:latest" --push src/worker

docker buildx build --platform linux/arm64 \
  -t "$ECR/claude-agent-dispatcher:latest" --push src/dispatcher
```

**Checkpoint:** both repositories list a `latest` image:

```bash
aws ecr list-images --repository-name claude-agent-worker --region "$AWS_REGION"
aws ecr list-images --repository-name claude-agent-dispatcher --region "$AWS_REGION"
```

---

## Module 3 — Deploy the sandbox infrastructure

Store the environment key as a Secret (prefer this over committing it; for production, source it from AWS Secrets Manager via the Secrets Store CSI driver or External Secrets Operator):

```bash
kubectl create namespace claude-agents --dry-run=client -o yaml | kubectl apply -f -
kubectl -n claude-agents create secret generic anthropic-env-key \
  --from-literal=ANTHROPIC_ENVIRONMENT_KEY="$ANTHROPIC_ENVIRONMENT_KEY"
```

Fill in the manifest placeholders, then apply the kustomization:

```bash
cd k8s
sed -i.bak "s|ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com|$ECR|g" sandboxtemplate-worker.yaml dispatcher.yaml
sed -i.bak "s|ENV_ID|$ANTHROPIC_ENVIRONMENT_ID|g" dispatcher.yaml
sed -i.bak "s|\${CLUSTER_NAME}|$CLUSTER_NAME|g" nodepool-gvisor.yaml
rm -f *.bak

kubectl apply -k .
```

**Checkpoint:** the dispatcher is polling and the warm pool has ready workers (give Karpenter ~2 minutes to provision a gVisor node on the first apply):

```bash
kubectl -n claude-agents get sandboxwarmpool,pods
```

```
NAME                                                            REPLICAS
sandboxwarmpool.extensions.agents.x-k8s.io/claude-agent-worker   2

NAME                                            READY   STATUS    RESTARTS   AGE
pod/claude-agent-dispatcher-xxxxxxxxxx-xxxxx    1/1     Running   0          2m
pod/claude-agent-worker-xxxxx                   1/1     Running   0          2m
pod/claude-agent-worker-yyyyy                   1/1     Running   0          2m
```

If a worker stays `Pending` past three minutes, Karpenter is still provisioning a gVisor node — check `kubectl -n claude-agents describe pod -l app=claude-agent-worker` for scale-up events.

---

## Module 4 — Pair a Managed Agent and verify

Authenticate the CLI, then unset the org API key so it doesn't shadow the OAuth token for interactive commands:

```bash
ant auth login
unset ANTHROPIC_API_KEY
```

Create an agent and a session bound to your environment:

```bash
AGENT_ID=$(ant beta:agents create \
  --name eks-sandbox-probe \
  --model '{"id":"claude-sonnet-4-6"}' \
  --system 'You run tools inside a self-hosted sandbox on EKS under gVisor. Use bash to inspect the environment when asked.' \
  --tool '{"type":"agent_toolset_20260401"}' \
  --format json --transform 'id' -r)

SESSION_ID=$(ant beta:sessions create \
  --agent '{"id":"'"$AGENT_ID"'","type":"agent"}' \
  --environment-id "$ANTHROPIC_ENVIRONMENT_ID" \
  --format json --transform 'id' -r)

echo "AGENT_ID=$AGENT_ID  SESSION_ID=$SESSION_ID"
```

Send a prompt that forces a tool call, wait, then read the answer:

```bash
ant beta:sessions:events send --session-id "$SESSION_ID" \
  --event '{"type":"user.message","content":[{"type":"text","text":"Run `uname -a && hostname` and tell me what sandbox you are executing in."}]}'

sleep 15

ant beta:sessions:events list --session-id "$SESSION_ID" --order asc --format jsonl \
  | jq -r 'select(.type=="agent.message") | .content[0].text'
```

**Checkpoint:** the model reports a gVisor kernel (the `4.4.0` string is gVisor's synthetic kernel signature) and a `claude-agent-worker-*` hostname — proof the `bash` ran on a pod in **your** cluster, not Anthropic's. Confirm from the cluster side:

```bash
kubectl -n claude-agents logs -l app=claude-agent-worker --tail=20 --prefix
```

Any session created with `--environment-id "$ANTHROPIC_ENVIRONMENT_ID"` now executes its tool calls here.

!!! note "ant 1.9.1 flag parsing"
    `--model` and `--agent` accept a string per `--help`, but ant 1.9.1 only parses the JSON object form — pass `'{"id":"..."}'`. Prefer `events list` over `events stream` for inspection; `stream` only emits events that arrive after it connects.

---

## Autoscaling the warm pool

The `SandboxWarmPool` ships at a fixed `replicas: 2`. For real traffic, scale it on queue depth. Two options:

- **HPA on the `/scale` subresource.** `SandboxWarmPool` exposes `/scale`, so a `HorizontalPodAutoscaler` can target it with a custom/external metric.
- **A stats-adapter sidecar.** A small process reads Anthropic's `work.stats` endpoint every ~15 s and patches the warm pool's replica count to match concurrent sessions. This path needs the **org API key** — keep it in the dispatcher namespace, never in a worker pod. See Anthropic's [GKE reference implementation](https://github.com/GoogleCloudPlatform/kubernetes-engine-samples/tree/main/ai-ml/anthropic-agent-sandbox) for a working `stats-adapter`.

---

## Security model — what you own

When you self-host, Anthropic secures only the control plane. These are **your** responsibilities (see [Anthropic's security model](https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes-security)):

- **Runtime hardening.** This recipe runs workers as non-root with a read-only root filesystem, all capabilities dropped, no mounted service-account token, and gVisor isolation. Keep those defaults.
- **Network egress.** The default-deny `NetworkPolicy` + allow-list is the base layer. Because `NetworkPolicy` can't match a hostname, the HTTPS rule is a broad `0.0.0.0/0:443`. Narrow it to `api.anthropic.com` with a hostname-aware control — AWS Network Firewall FQDN rules, a Cilium `toFQDNs` policy, or an egress proxy.
- **Key storage and rotation.** The environment key belongs in a secrets manager, not an image. Rotate it immediately on any suspected exposure — revocation takes effect on the worker's next call.
- **Trust-boundary isolation.** The environment key is scoped to one environment's queue. For untrusted multi-tenant workloads, provision a separate workspace and environment per trust boundary so each key maps to a single tenant's sessions.
- **Session data.** Conversation content and tool outputs flow through your worker and the `/mnt/session/outputs` PVC. Retaining, redacting, or deleting that data is on you.
- **Memory stores.** The worker keeps a working copy under `/mnt/memory/` for the session and deletes it on teardown. A worker that exits without teardown can leave a copy behind — clean up leftover copies and keep that path isolated between sessions.

---

## Clean up

```bash
# Delete Anthropic sessions
ant beta:sessions list --format jsonl | jq -r '.id' \
  | xargs -I{} ant beta:sessions delete --session-id {}

# Remove cluster resources
kubectl -n claude-agents delete sandboxclaim --all
kubectl delete -k k8s
kubectl delete namespace claude-agents
```

Delete the ECR repositories and the self-hosted environment in the Anthropic Console if you no longer need them.

---

## What's next

- **Give the agent internal tools.** Point your egress policy at your own internal services, or bake custom tools / an in-network MCP server into the worker image (`src/worker/`). That is the whole point of self-hosting.
- **Harden egress** to exactly `api.anthropic.com` with a hostname-aware control.
- **Add autoscaling** so the warm pool tracks demand.

## References

- [Anthropic — Self-hosted sandboxes](https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes)
- [Anthropic — Self-hosted sandbox security model](https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes-security)
- [Agent Sandbox — Anthropic Managed Agents use case](https://agent-sandbox.sigs.k8s.io/docs/use-cases/anthropic-managed-agents/)
- [GKE reference implementation](https://github.com/GoogleCloudPlatform/kubernetes-engine-samples/tree/main/ai-ml/anthropic-agent-sandbox)
- [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox)
