# KV-Aware Routing on Amazon EKS with NVIDIA Dynamo (2× g6e.xlarge) — Lab Guide

This hands-on lab serves **Qwen3-8B** from two GPU workers behind **NVIDIA Dynamo's KV-aware router** on **Amazon EKS Auto Mode**, and measures what the router buys you compared with round-robin. It uses:

- The **AWS vLLM Deep Learning Container** (vLLM 0.26.0) for every Dynamo pod.
- **Amazon EFS** (through the EFS CSI driver add-on) as one shared, ReadWriteMany model volume for every pod, read by **Run:ai Model Streamer** straight into GPU memory.
- **DCGM Exporter + Prometheus + Grafana** for observability: the NVIDIA DCGM dashboard plus a lab dashboard that puts prefix-cache hit rate, TTFT, and GPU activity side by side.

Target region: **us-east-2** (any region with g6e.xlarge works). GPUs: **2× g6e.xlarge**, each with 1× NVIDIA L40S 48 GB, 4 vCPU, and 32 GiB memory, on-demand.

> This lab is the companion to [Disaggregated Inference (Dynamo)](../dynamo-disaggregated/index.md). That lab splits **prefill and decode** across GPUs. This one keeps each request on one GPU (aggregated serving) and focuses on **which GPU** gets it.

---

## Why KV-aware routing

Every request's prompt is turned into KV-cache blocks during prefill. vLLM keeps those blocks after the request ends (**prefix caching**): a later prompt that starts with the same tokens skips recomputing them. Real traffic is full of shared prefixes, such as system prompts, RAG context, tool definitions, and multi-turn chat history.

With more than one worker, the cache is only useful if the request lands on the worker that **has** it:

| Router | What it does with a repeat prefix | Effective cache |
|--------|-----------------------------------|-----------------|
| **Round-robin / random** | Sends it to whichever worker is next, which often lacks the prefix and recomputes it. Every worker ends up caching every tenant | Each GPU must hold the **whole** working set |
| **Dynamo KV router** | Sends it to the worker whose cache already holds the most matching blocks, weighed against that worker's current load | The working set is **partitioned**: the GPUs' caches add up |

How the Dynamo KV router knows what each GPU has cached:

1. Each vLLM worker publishes **KV events** (`BlockStored` / `BlockRemoved`) over ZMQ (`--kv-events-config`). Dynamo relays them to the router.
2. The frontend tokenizes the incoming prompt, hashes it into blocks, and looks the hashes up in a radix tree of every worker's blocks.
3. It scores each worker as `prefill_load_scale × (prompt blocks − overlap_credit × cached blocks) + active decode blocks` and picks the lowest score.

So the router removes **redundant prefill**: lower TTFT, fewer tensor-core cycles spent recomputing the same prefix, and more throughput from the same GPUs.

---

## Architecture

```text
                          Amazon EKS Auto Mode (us-east-2)
┌───────────────────────────────────────────────────────────────────────────┐
│  general-purpose NodePool (built-in)                                      │
│   ┌─────────────────────────┐  ┌─────────────────────────┐                │
│   │ Frontend   (KV router)  │  │ FrontendRR (round-robin)│  :8000 each    │
│   │ DYN_ROUTER_MODE=kv      │  │ baseline, same workers  │  OpenAI API    │
│   └────────────┬────────────┘  └────────────┬────────────┘                │
│                │   ▲ KV events (stored/removed blocks)                    │
│   Dynamo operator · NATS · Prometheus · Grafana │                         │
│                ▼   │                        ▼                             │
│  gpu-g6e-xl NodePool (this lab)                                           │
│   ┌──────────────────────────┐   ┌──────────────────────────┐             │
│   │ VllmWorker #1            │   │ VllmWorker #2            │             │
│   │ g6e.xlarge · 1x L40S     │   │ g6e.xlarge · 1x L40S     │             │
│   │ AWS vLLM DLC + Dynamo    │   │ AWS vLLM DLC + Dynamo    │             │
│   │ dcgm-exporter            │   │ dcgm-exporter            │             │
│   └────────────▲─────────────┘   └────────────▲─────────────┘             │
└────────────────┼──────────────────────────────┼───────────────────────────┘
                 └──── Run:ai Model Streamer ───┘
                  Amazon EFS  /models/Qwen3-8B  (PVC model-cache, ReadWriteMany,
                              read-only in every pod; frontends read the tokenizer)
```

| Piece | Role |
|-------|------|
| **AWS vLLM DLC** `vllm:0.26.0-…-ec2-v1.4-…-soci` | vLLM 0.26.0 (the version Dynamo 1.4.0 is built against), PyTorch, CUDA 13, NIXL, and runai-model-streamer. It is a SOCI image, so Auto Mode starts it before the full 9 GB pull finishes |
| **`dlc-dynamo-entrypoint.sh`** | Installs the `ai-dynamo==1.4.0` wheels into the DLC at start-up, without touching vLLM (takes about 15 s), then starts `dynamo.frontend` or `dynamo.vllm` |
| **EFS volume `model-cache`** | One Amazon EFS file system, mounted through the EFS CSI driver add-on. A one-off Job downloads Qwen3-8B onto it; workers and frontends mount it read-only, so every pod sees the same files |
| **`Frontend` / `FrontendRR`** | Two OpenAI-compatible frontends in front of the **same** two workers, so you can A/B the router without redeploying |
| **`VllmWorker` ×2** | Aggregated vLLM workers, one per g6e.xlarge, publishing KV events |
| **DCGM Exporter** | GPU telemetry per node, mapped to the worker pod using the GPU |

---

## Prerequisites

- **AWS CLI** v2, **kubectl** (v1.30+), **eksctl** (v0.200.0+ for Auto Mode), **Helm** v3, and **Python 3.9+** (for the benchmark; standard library only).
- Quota for **"Running On-Demand G and VT instances"** of at least **8 vCPUs** (2× g6e.xlarge).
- **No Hugging Face token required.** Qwen3-8B is public. A token only avoids anonymous rate limits on the one-time download.

> **Cost.** You pay for two on-demand g6e.xlarge only while the workers run, plus 5 minutes of idle time before Auto Mode removes them. You also pay for the EKS cluster, the general-purpose Auto Mode nodes, EBS volumes, and the EFS file system: about 16 GB of storage, plus Elastic Throughput charges for the data written once and read on every worker start. Check the [AWS Pricing Calculator](https://calculator.aws/) and run the cleanup step.

---

## Step 0 — Get the lab files

```bash
git clone https://github.com/awslabs/accelerated-compute-tutorials.git
cd accelerated-compute-tutorials/docs/en/ai-infra/orchestration/dynamo-kv-routing
```

All commands below run from this directory.

---

## Step 1 — Create the EKS Auto Mode cluster

```bash
export AWS_REGION="us-east-2"
export CLUSTER_NAME="dynamo-kv-lab"
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Confirm g6e.xlarge is offered in the region (lists the AZs):
aws ec2 describe-instance-type-offerings --region ${AWS_REGION} \
  --location-type availability-zone \
  --filters Name=instance-type,Values=g6e.xlarge \
  --query 'InstanceTypeOfferings[*].Location' --output text

eksctl create cluster -f manifests/eksctl-cluster.yaml
```

If you change `CLUSTER_NAME` or `AWS_REGION`, also change `metadata.name` and `metadata.region` in `manifests/eksctl-cluster.yaml`. Creation takes about 15 minutes. When it finishes, eksctl configures `kubectl`.

Add the StorageClass (for the NATS PVC) and the GPU NodePool:

```bash
kubectl apply -f manifests/auto-ebs-sc.yaml
kubectl apply -f manifests/gpu-nodepool.yaml
kubectl get nodepool gpu-g6e-xl     # READY True; 0 nodes until the workers are scheduled
```

The `gpu-g6e-xl` NodePool allows only on-demand `g6e.xlarge`. Its limit of `nvidia.com/gpu: "2"` caps it at two nodes. It taints the nodes with `nvidia.com/gpu:NoSchedule`, and it removes a node 5 minutes after the node becomes empty.

---

## Step 2 — Put the model on a shared EFS volume

Every worker and frontend mounts the same Amazon EFS file system read-only at `/models`. A one-off Job fills it from Hugging Face. Auto Mode includes the EBS CSI driver but **not** the EFS one, so first install the `aws-efs-csi-driver` EKS add-on. Its controller gets AWS credentials through **EKS Pod Identity**, which Auto Mode includes.

### 2a. Install the EFS CSI driver add-on

```bash
# IAM role for the driver's controller. Create it before the add-on, so the
# controller pods get credentials when they start.
eksctl create podidentityassociation --cluster ${CLUSTER_NAME} --region ${AWS_REGION} \
  --namespace kube-system --service-account-name efs-csi-controller-sa \
  --role-name "${CLUSTER_NAME}-efs-csi" \
  --permission-policy-arns arn:aws:iam::aws:policy/service-role/AmazonEFSCSIDriverPolicy

# Latest add-on version for the cluster's Kubernetes version:
EFS_ADDON_VERSION=$(aws eks describe-addon-versions --region ${AWS_REGION} \
  --addon-name aws-efs-csi-driver --kubernetes-version 1.37 \
  --query 'addons[0].addonVersions[0].addonVersion' --output text)   # e.g. v3.5.3-eksbuild.1

aws eks create-addon --cluster-name ${CLUSTER_NAME} --region ${AWS_REGION} \
  --addon-name aws-efs-csi-driver --addon-version ${EFS_ADDON_VERSION}
aws eks wait addon-active --cluster-name ${CLUSTER_NAME} --region ${AWS_REGION} \
  --addon-name aws-efs-csi-driver

kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-efs-csi-driver
# efs-csi-controller-... x2 and one efs-csi-node-... per node, all Running
```

The `efs-csi-node` DaemonSet tolerates every taint, so it also runs on the GPU nodes when they come up.

### 2b. Create the file system and mount targets

The file system lives in the cluster VPC. It needs a security group that allows NFS (TCP 2049) from the VPC, and one mount target in each Availability Zone where Auto Mode can launch nodes. The commands read those AZs and subnets from the built-in `default` NodeClass, which the GPU NodePool also uses.

```bash
VPC_ID=$(aws eks describe-cluster --name ${CLUSTER_NAME} --region ${AWS_REGION} \
  --query cluster.resourcesVpcConfig.vpcId --output text)
VPC_CIDR=$(aws ec2 describe-vpcs --vpc-ids ${VPC_ID} --region ${AWS_REGION} \
  --query 'Vpcs[0].CidrBlock' --output text)

EFS_SG=$(aws ec2 create-security-group --region ${AWS_REGION} --vpc-id ${VPC_ID} \
  --group-name "${CLUSTER_NAME}-efs" --description "NFS from ${CLUSTER_NAME} nodes" \
  --query GroupId --output text)
aws ec2 authorize-security-group-ingress --region ${AWS_REGION} --group-id ${EFS_SG} \
  --protocol tcp --port 2049 --cidr ${VPC_CIDR}

export EFS_ID=$(aws efs create-file-system --region ${AWS_REGION} \
  --performance-mode generalPurpose --throughput-mode elastic --encrypted \
  --tags Key=Name,Value=${CLUSTER_NAME}-models \
  --query FileSystemId --output text)
until [ "$(aws efs describe-file-systems --region ${AWS_REGION} --file-system-id ${EFS_ID} \
  --query 'FileSystems[0].LifeCycleState' --output text)" = available ]; do sleep 5; done

# One mount target per AZ the nodes use:
kubectl get nodeclass default \
  -o jsonpath='{range .status.subnets[*]}{.zone} {.id}{"\n"}{end}' | sort -u -k1,1 |
while read -r az subnet; do
  echo "${az}: $(aws efs create-mount-target --region ${AWS_REGION} --file-system-id ${EFS_ID} \
    --subnet-id ${subnet} --security-groups ${EFS_SG} --query MountTargetId --output text)"
done

until [ -z "$(aws efs describe-mount-targets --region ${AWS_REGION} --file-system-id ${EFS_ID} \
  --query "MountTargets[?LifeCycleState!='available'].MountTargetId" --output text)" ]; do sleep 10; done
aws efs describe-mount-targets --region ${AWS_REGION} --file-system-id ${EFS_ID} \
  --query 'MountTargets[].[AvailabilityZoneName,LifeCycleState]' --output table
```

Elastic Throughput scales with demand, so there is no throughput to provision. If nodes use secondary VPC CIDRs, allow TCP 2049 from those too.

### 2c. Create the PVC and download the model

`manifests/efs-model-storage.yaml` defines an `efs-sc` StorageClass, a PersistentVolume that points at the file system, and the `model-cache` PVC (ReadWriteMany) in `dynamo-system`:

```bash
kubectl create namespace dynamo-system

sed -i.bak "s|REPLACE_WITH_EFS_ID|${EFS_ID}|" manifests/efs-model-storage.yaml
kubectl apply -f manifests/efs-model-storage.yaml
kubectl get pvc model-cache -n dynamo-system     # STATUS Bound
```

Optionally add a Hugging Face token. The download Job reads it if it exists:

```bash
kubectl create secret generic hf-token-secret -n dynamo-system --from-literal=HF_TOKEN=hf_xxx
```

Run the download. It takes about 5–10 minutes for ~16 GB, on a general-purpose node:

```bash
kubectl apply -f manifests/model-download-job.yaml
kubectl logs -n dynamo-system -f job/qwen3-8b-to-efs     # ends with DOWNLOAD_COMPLETE
# config.json, generation_config.json, model-0000{1..5}-of-00005.safetensors,
# model.safetensors.index.json, tokenizer.json, tokenizer_config.json, vocab.json, merges.txt
```

The model is now at `/models/Qwen3-8B` on the volume. The Job needs no AWS credentials: the EFS CSI driver does the mount, and the pod only talks to Hugging Face.


---

## Step 3 — Install the monitoring stack (Prometheus, Grafana, DCGM)

Install monitoring **before** the GPU nodes come up, so the first model load is captured on the dashboards.

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add gpu-helm-charts https://nvidia.github.io/dcgm-exporter/helm-charts
helm repo update

helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --version 92.17.1 --namespace monitoring --create-namespace \
  -f manifests/monitoring/kube-prometheus-stack-values.yaml

helm upgrade --install dcgm-exporter gpu-helm-charts/dcgm-exporter \
  --version 4.8.4 --namespace monitoring \
  -f manifests/monitoring/dcgm-exporter-values.yaml

kubectl apply -f manifests/monitoring/kv-routing-dashboard.yaml
```

`helm upgrade --install` also works if a release from an earlier lab already exists on the cluster; plain `helm install` would fail with `cannot re-use a name that is still in use`. Make sure the last command (the dashboard ConfigMap) runs too.

What you get:

- **kube-prometheus-stack**: Prometheus, Grafana, kube-state-metrics, and node-exporter. Prometheus picks up every ServiceMonitor and PodMonitor in the cluster. Grafana pre-loads the official **NVIDIA DCGM Exporter Dashboard** ([12239](https://grafana.com/grafana/dashboards/12239)) into the **GPU** folder.
- **dcgm-exporter**: a DaemonSet that selects `eks.amazonaws.com/instance-gpu-manufacturer=nvidia` and tolerates the GPU taint. Auto Mode already provides the driver and device plugin, so the GPU Operator is not needed. The DaemonSet shows `DESIRED 0` until the g6e nodes join:

    ```bash
    kubectl get ds dcgm-exporter -n monitoring
    ```

- **Dynamo KV-Aware Routing (lab)** dashboard: per-worker prefix-cache hit rate, per-worker prefill tokens, per-frontend TTFT, and DCGM utilization, tensor activity, memory, and power.

Open Grafana. The user is `admin` and the password is `dynamo-lab`, set in the values file; change it for anything beyond a lab:

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80 &
# http://localhost:3000
```

---

## Step 4 — Install the NVIDIA Dynamo platform

The Dynamo platform Helm chart installs the operator, NATS, and the CRDs:

```bash
export DYNAMO_VERSION="1.4.0"
helm fetch https://helm.ngc.nvidia.com/nvidia/ai-dynamo/charts/dynamo-platform-${DYNAMO_VERSION}.tgz

helm install dynamo-platform dynamo-platform-${DYNAMO_VERSION}.tgz \
  --namespace dynamo-system

kubectl get pods -n dynamo-system
# dynamo-platform-dynamo-operator-controller-manager-...  Running
# dynamo-platform-nats-0                                   Running
```

---

## Step 5 — Deploy the KV-routed graph

Load the entrypoint script into a ConfigMap, then apply the graph. The graph has no placeholders: every pod mounts the `model-cache` PVC from Step 2.

```bash
kubectl create configmap dynamo-dlc-launcher -n dynamo-system \
  --from-file=scripts/dlc-dynamo-entrypoint.sh

kubectl apply -f manifests/qwen3-8b-kv-router.yaml
```

> **Metrics need no extra step.** The Dynamo platform chart from Step 4 installs PodMonitors (`dynamo-frontend`, `dynamo-worker`, `dynamo-router`, `dynamo-planner`) that scrape every Dynamo pod with the label `nvidia.com/metrics-enabled=true`, which the operator sets, every 5 s. The lab dashboard reads those jobs (`job="dynamo-system/dynamo-frontend"` and `job="dynamo-system/dynamo-worker"`) and picks this graph's pods by name. This relies on Step 3 running first: `dynamo-operator.dynamo.metrics.podMonitors.enabled` defaults to auto-detect, so the chart creates the PodMonitors only if the Prometheus Operator CRDs already exist (set it to `true` to force them).

What `qwen3-8b-kv-router.yaml` sets up:

**Workers** (`VllmWorker`, 2 replicas, 1 GPU each, so one per g6e.xlarge):

| Flag | Why |
|------|-----|
| `--model /models/Qwen3-8B --load-format runai_streamer` | The EFS volume, mounted read-only. Run:ai Model Streamer reads the safetensors with 16 concurrent large-block reads and copies them straight into GPU memory, instead of vLLM's default single-stream mmap reads. A local directory also means `dynamo.vllm` skips its Hugging Face pre-fetch |
| `--model-loader-extra-config '{"concurrency":16,"memory_limit":8589934592}'` | Caps the streamer's CPU staging buffer at 8 GiB, so it fits in a g6e.xlarge's 32 GiB |
| `--served-model-name Qwen/Qwen3-8B` | The name clients use (otherwise it would be the path `/models/Qwen3-8B`) |
| `--enable-prefix-caching` | vLLM keeps KV blocks after a request ends, so a matching prefix is reused |
| `--kv-events-config '{"publisher":"zmq",…,"enable_kv_cache_events":true}'` | Publishes block stored/removed events. **Without this, the KV router can only guess** |
| `--num-gpu-blocks-override 2048` | **Lab knob.** Caps each GPU's KV cache at 2048 × 16 = **32,768 tokens**. An L40S would otherwise hold ~170K tokens of Qwen3-8B KV. Then the benchmark would need a much larger working set before routing matters. The cap makes a 5-minute benchmark behave like a busy production fleet, where the working set exceeds one GPU's cache |

**Frontends.** Both run `dynamo.frontend` from the same DLC image on CPU nodes:

| Component | Service | Router |
|-----------|---------|--------|
| `Frontend` | `qwen3-8b-kv-frontend` | `DYN_ROUTER_MODE=kv`, with the cost-model knobs `DYN_ROUTER_KV_OVERLAP_SCORE_CREDIT=4.0` (Dynamo's default is 1.0; see Step 8 for why the lab raises it) and `DYN_ROUTER_PREFILL_LOAD_SCALE=1.0` |
| `FrontendRR` | `qwen3-8b-kv-frontendrr` | `DYN_ROUTER_MODE=round-robin` |

Each frontend mounts the same EFS volume read-only and gets `--model-path /models/Qwen3-8B`. It needs the tokenizer and config files to tokenize prompts and hash them into blocks, and it reads exactly the files the workers loaded.

Watch it come up. On the first start, Auto Mode launches two g6e.xlarge. The SOCI image starts in about a minute, and Dynamo installs in about 15 s. The weights then stream from EFS, and vLLM compiles and captures CUDA graphs:

```bash
kubectl get nodeclaims -w                                   # two g6e.xlarge
kubectl get pods -n dynamo-system -o wide -w                # 2 frontends + 2 workers -> Running/Ready

kubectl logs -n dynamo-system -f \
  -l nvidia.com/dynamo-graph-deployment-name=qwen3-8b-kv,nvidia.com/dynamo-component-type=worker \
  --max-log-requests=4
```

In the worker logs, look for:

- `[lab] versions: {'ai-dynamo': '1.4.0', 'ai-dynamo-runtime': '1.4.0', 'vllm': '0.26.0', ...}`
- `Loading safetensors using Runai Model Streamer`, then `Model loading took ~15.3 GiB memory and N seconds`. The time depends on EFS throughput to each node; both workers read the same files at the same time on the first start.
- `# GPU blocks: 2048`, which confirms the lab cap.

---

## Step 6 — Smoke test

```bash
kubectl port-forward -n dynamo-system svc/qwen3-8b-kv-frontend   8000:8000 &
kubectl port-forward -n dynamo-system svc/qwen3-8b-kv-frontendrr 8001:8000 &

curl -s localhost:8000/v1/models | python3 -m json.tool       # "id": "Qwen/Qwen3-8B"

curl -s localhost:8000/v1/chat/completions -H 'Content-Type: application/json' -d '{
  "model": "Qwen/Qwen3-8B",
  "messages": [{"role": "user", "content": "In one sentence, what is KV-aware routing?"}],
  "max_tokens": 64, "chat_template_kwargs": {"enable_thinking": false}}' | python3 -m json.tool
```

If `kubectl get svc -n dynamo-system` shows different frontend service names, use those.

Check that the KV router sees both workers and their KV events. The frontend logs list the workers it discovered and the block size it uses for hashing:

```bash
kubectl logs -n dynamo-system -l nvidia.com/dynamo-component=Frontend --tail=100 | grep -iE "kv|router|worker"
```

---

## Step 7 — A/B: round-robin vs KV-aware routing

The benchmark simulates **8 tenants**. Each has its own ~5,500-token system prompt, and the tenants **take turns**: each round, every tenant sends one request, in a new random order, for 160 requests (20 rounds). This is how chat sessions or agent loops behave, where a user comes back after the others have had their turn. All 8 prefixes need ~44K tokens of KV, more than one GPU's 32K-token cache but less than the 64K of both together:

- **Round-robin** puts every tenant on both GPUs. Each GPU tries to hold all 44K tokens in 32K, so the least recently used prefixes keep getting evicted. Taking turns is the worst case for that: by the time a tenant comes back, the other seven have had their turn and its prefix is usually gone, or the request lands on the GPU that never had it.
- **KV routing** keeps each tenant on one GPU, so each GPU needs only about 22K tokens. The router also weighs load, so under concurrency it sometimes sends a repeat to the other worker, which then has to prefill it and cache it there too. The lab's overlap credit of 4.0 keeps that rare (Step 8); the KV router reduces misses, it does not remove them.

Few, long prefixes make the difference easy to see: a miss is a full ~5,500-token prefill (about 450 ms on an L40S), a hit is about 70 ms.

### Run the A/B

Run the benchmark once against each frontend, from the lab directory. Each command starts a throwaway pod **inside the cluster** (so the numbers don't include network time from your laptop) and streams the script into it. `--worker-metrics` points the script at the two workers' metrics endpoints, so it also prints the server-side prefix-cache hit rate for exactly that run:

```bash
WORKER_METRICS=$(kubectl get pod -n dynamo-system -l nvidia.com/dynamo-component-type=worker \
  -o jsonpath='{range .items[*]}http://{.status.podIP}:9090,{end}')

# KV-aware router
kubectl run kv-bench -n dynamo-system --rm -i --restart=Never \
  --image=public.ecr.aws/docker/library/python:3.12-slim -- \
  python3 - --url http://qwen3-8b-kv-frontend:8000 --label kv-router --seed 101 \
  --worker-metrics ${WORKER_METRICS} < scripts/kv_routing_bench.py

# Round-robin
kubectl run kv-bench -n dynamo-system --rm -i --restart=Never \
  --image=public.ecr.aws/docker/library/python:3.12-slim -- \
  python3 - --url http://qwen3-8b-kv-frontendrr:8000 --label round-robin --seed 202 \
  --worker-metrics ${WORKER_METRICS} < scripts/kv_routing_bench.py
```

Each run takes under a minute. Use a **new `--seed` every time** you re-run: the seed generates the tenant prompts, so a new seed means no run benefits from cache left by an earlier one.

### Read the results

This is one measured pair on 2× g6e.xlarge, using the defaults above:

```text
[kv-router] results  (wall 38.3s, 4.18 req/s, failures=0)
  prompt length          ~5481 tokens/request
  TTFT first-touch         n=8    mean=    680 ms  p50=    736 ms  p90=    923 ms  p99=    955 ms
  TTFT repeat (cacheable)  n=152  mean=    119 ms  p50=     74 ms  p90=    312 ms  p99=    508 ms
  end-to-end latency       n=160  mean=    948 ms  p50=    864 ms  p90=   1258 ms  p99=   1692 ms
  prefix-cache hit http://192.168.161.65:9090    86.4%  (449,382 prompt tokens)
  prefix-cache hit http://192.168.180.193:9090   87.8%  (427,634 prompt tokens)
  prefix-cache hit (all workers)       87.1%  (ceiling ~95%: first touches always miss)

[round-robin] results  (wall 47.6s, 3.36 req/s, failures=0)
  prompt length          ~5481 tokens/request
  TTFT first-touch         n=8    mean=    666 ms  p50=    565 ms  p90=    930 ms  p99=    954 ms
  TTFT repeat (cacheable)  n=152  mean=    240 ms  p50=     89 ms  p90=    520 ms  p99=    604 ms
  end-to-end latency       n=160  mean=   1175 ms  p50=   1215 ms  p90=   1698 ms  p99=   1974 ms
  prefix-cache hit http://192.168.161.65:9090    62.6%  (438,551 prompt tokens)
  prefix-cache hit http://192.168.180.193:9090   57.5%  (438,459 prompt tokens)
  prefix-cache hit (all workers)       60.0%  (ceiling ~95%: first touches always miss)
```

Across repeated pairs, the KV router measured 85–87% prefix-cache hits against 60–70% for round-robin, with a 35–50% lower mean repeat TTFT, a 35–40% lower p90, and 15–25% more requests per second from the same two GPUs.

What each line means:

- **`TTFT first-touch`** is a tenant's first request. It is a full prefill under both routers, so it should be similar in both runs. All 8 arrive in the first round at once, so they queue behind each other (hence ~700 ms, not ~450 ms).
- **`TTFT repeat (cacheable)`** is the number that matters. Each repeat is either a **hit** (about 70 ms: the short question plus one decode step) or a **miss** (a full prefill, about 450–500 ms). Read it that way:
    - **p50** is a hit for both routers.
    - **p90** is a miss for round-robin (~520 ms), but still mostly a hit for the KV router (~310 ms).
    - The **mean** combines both: 35–50% lower for the KV router in the measured pairs, because far fewer repeats fall into the miss cluster.
- **`req/s`** and **end-to-end latency** improve with the KV router, because the GPUs spend less time recomputing prefixes.
- **`prefix-cache hit`** is vLLM's own counter (tokens served from cache ÷ prompt tokens) on each worker, for this run only. 8 of the 160 requests are first touches, so the ceiling is about 95%.
- **`prompt length`** should be about 5,500 tokens. Much more, and 8 tenants no longer fit in the two caches together, so the KV router starts evicting as well. Lower `--prefix-words` (default 3300) or `--tenants` (default 8) to get back to the design point.

A single pair can be noisy. If the KV router's mean repeat TTFT is not clearly lower, run both commands again with new seeds; if it keeps losing, check the troubleshooting row "KV router only slightly better". The prefix-cache hit rate in the output and in Grafana (next section) shows the cause directly.

> Exact numbers depend on your run. The gap is widest when the working set is larger than one GPU's cache but clearly smaller than both together, and when tenants take turns rather than arriving at random. It disappears if everything fits in each GPU (for example after removing `--num-gpu-blocks-override`), and also if the working set overflows both GPUs. `--pattern random` picks tenants at random instead: hot tenants then recur quickly and stay cached even under round-robin, so the gap is smaller.

### Watch it in Grafana

Open **Dashboards → Dynamo KV-Aware Routing (lab)** and set the time range to **Last 15 minutes**. Each benchmark run shows up as a separate burst of traffic, in the order you ran them; the **Requests/s by frontend** panel shows which frontend each burst went through (`kv-router` = `Frontend`, `round-robin` = `FrontendRR`). The server-side panels confirm *why* the KV router is faster, independent of where the benchmark ran:

| Panel | Round-robin run | KV-router run |
|-------|----------------|---------------|
| Prefix-cache hit rate per worker | Lower (60–70% in the measured runs): evictions | Higher (85–87%) |
| Prompt tokens actually computed | Higher on both workers | Lower: fewer prefixes recomputed |
| KV cache usage per worker | Blocks held by running requests only (about 20% here); cached-but-idle blocks do not count | Similar |
| TTFT p50 / p90 by frontend | Fast p50, p90 at full-prefill time | Fast p50; p90 still shows the remaining misses |
| Tensor pipe active (DCGM) | Higher: prefill recompute | Somewhat lower for the same request rate |
| Requests/s per worker | Perfectly even | Roughly even. The router trades a little balance for cache hits |

Open **Dashboards → GPU → NVIDIA DCGM Exporter Dashboard** for the standard per-GPU view: temperature, power, SM clocks, utilization, framebuffer, and tensor core utilization. Each GPU series carries the worker pod in the **`exported_pod`** label (`pod` is the exporter's own pod), and the node in **`hostname`**, because dcgm-exporter maps GPUs to pods through the kubelet pod-resources API.

You can also query the raw metrics in Prometheus:

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090 &
# http://localhost:9090
#   sum by (pod) (rate(vllm:prefix_cache_hits_total{job="dynamo-system/dynamo-worker"}[1m])) / sum by (pod) (rate(vllm:prefix_cache_queries_total{job="dynamo-system/dynamo-worker"}[1m]))
#   DCGM_FI_DEV_GPU_UTIL
```

---

## Step 8 (optional) — Tune the router

The KV router's cost per worker is:

```text
cost = prefill_load_scale × (prompt_blocks − overlap_credit × cached_blocks) + active_decode_blocks
```

With credit 1.0 (Dynamo's default), a cached block only cancels its own prefill cost. If the worker that holds a tenant is busy prefilling another ~5,500-token prompt, the idle worker scores lower, even though it must recompute the whole prefix, and the tenant ends up cached on both GPUs. With long prefixes and concurrency 4, that measured **66–67% hits for the KV router, barely above round-robin's 62%**. The lab sets the credit to **4.0**, so a cache hit outweighs a few in-flight requests of load difference; that measured 85–90%, with requests still split evenly across the workers.

Change the `Frontend` env in `qwen3-8b-kv-router.yaml` and re-apply. Only the frontend restarts; the workers and their caches stay up:

| Setting | Effect to look for |
|---------|-------------------|
| `DYN_ROUTER_KV_OVERLAP_SCORE_CREDIT=1.0` | Dynamo's default. Hit rate drops to near round-robin under concurrency (see above) |
| `DYN_ROUTER_KV_OVERLAP_SCORE_CREDIT=0.0` | Cache ignored; routing is driven by load only. Hit rate and TTFT should fall back toward round-robin |
| `DYN_ROUTER_PREFILL_LOAD_SCALE=2.0` | Steers new prompts away from a worker already busy prefilling |
| `--concurrency 1` on the benchmark | No load to balance: the KV router reaches its ceiling with any credit, which isolates the cache effect from the load trade-off |
| `--concurrency 16` on the benchmark | Shows load-vs-cache trade-offs once one worker gets busy |
| `--pattern random` on the benchmark | Tenants arrive at random instead of taking turns; round-robin keeps hot tenants cached by chance, so the gap shrinks |

Re-run the Step 7 kv-router command (with a new `--seed`) after each change. See [KV-aware routing — tuning](https://docs.dynamo.nvidia.com/dynamo/kubernetes/kv-aware-routing/using-the-dynamo-frontend) for every flag.

---

## Step 9 — Cleanup (do not skip)

```bash
pkill -f "kubectl port-forward" || true

kubectl delete -f manifests/qwen3-8b-kv-router.yaml --ignore-not-found     # GPU nodes go away ~5 min later
kubectl delete -f manifests/model-download-job.yaml --ignore-not-found
kubectl delete configmap dynamo-dlc-launcher -n dynamo-system --ignore-not-found

helm uninstall dynamo-platform -n dynamo-system
kubectl delete pvc -n dynamo-system --all
helm uninstall dcgm-exporter -n monitoring
helm uninstall kube-prometheus-stack -n monitoring
kubectl delete -f manifests/monitoring/kv-routing-dashboard.yaml --ignore-not-found

kubectl delete -f manifests/efs-model-storage.yaml --ignore-not-found    # PV is Retain: the data stays until the file system is deleted
aws eks delete-addon --cluster-name ${CLUSTER_NAME} --region ${AWS_REGION} --addon-name aws-efs-csi-driver

kubectl delete -f manifests/gpu-nodepool.yaml
kubectl delete -f manifests/auto-ebs-sc.yaml

# EFS: delete it BEFORE the cluster. Its mount-target ENIs and security group
# live in the cluster VPC and would block eksctl from deleting the VPC.
VPC_ID=$(aws eks describe-cluster --name ${CLUSTER_NAME} --region ${AWS_REGION} \
  --query cluster.resourcesVpcConfig.vpcId --output text)
EFS_ID=$(aws efs describe-file-systems --region ${AWS_REGION} \
  --query "FileSystems[?Name=='${CLUSTER_NAME}-models'].FileSystemId" --output text)
EFS_SG=$(aws ec2 describe-security-groups --region ${AWS_REGION} \
  --filters Name=vpc-id,Values=${VPC_ID} Name=group-name,Values=${CLUSTER_NAME}-efs \
  --query 'SecurityGroups[0].GroupId' --output text)

for mt in $(aws efs describe-mount-targets --region ${AWS_REGION} --file-system-id ${EFS_ID} \
    --query 'MountTargets[].MountTargetId' --output text); do
  aws efs delete-mount-target --region ${AWS_REGION} --mount-target-id ${mt}
done
until [ "$(aws efs describe-mount-targets --region ${AWS_REGION} --file-system-id ${EFS_ID} \
  --query 'length(MountTargets)' --output text)" = 0 ]; do sleep 10; done
aws efs delete-file-system --region ${AWS_REGION} --file-system-id ${EFS_ID}
aws ec2 delete-security-group --region ${AWS_REGION} --group-id ${EFS_SG}   # retry after a minute if ENIs are still detaching

eksctl delete cluster --name ${CLUSTER_NAME} --region ${AWS_REGION}

# EFS CSI driver IAM role (eksctl usually removes it with the cluster)
for p in $(aws iam list-attached-role-policies --role-name ${CLUSTER_NAME}-efs-csi --query 'AttachedPolicies[].PolicyArn' --output text 2>/dev/null); do
  aws iam detach-role-policy --role-name ${CLUSTER_NAME}-efs-csi --policy-arn $p
done
aws iam delete-role --role-name ${CLUSTER_NAME}-efs-csi 2>/dev/null || true
```

Confirm in the EC2 console that no g6e.xlarge instances remain.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Workers `Pending`, no NodeClaim | GPU quota, or NodePool not ready | `kubectl describe pod`; check the G and VT vCPU quota (needs 8); `kubectl describe nodepool gpu-g6e-xl` |
| Pods stuck `ContainerCreating`: `driver name efs.csi.aws.com not found in the list of registered CSI drivers` | EFS CSI add-on missing, or its node pod not yet running on that node | `aws eks describe-addon --cluster-name ${CLUSTER_NAME} --addon-name aws-efs-csi-driver`; `kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-efs-csi-driver -o wide` |
| Pods stuck `ContainerCreating`: `MountVolume.SetUp failed ... Connection timed out` | No mount target in the node's AZ, or the EFS security group does not allow TCP 2049 from the node | `aws efs describe-mount-targets --file-system-id ${EFS_ID}` must list every AZ in `kubectl get nodes -L topology.kubernetes.io/zone`; check the `${CLUSTER_NAME}-efs` inbound rule |
| PVC `model-cache` stays `Pending` | PV missing, or `REPLACE_WITH_EFS_ID` not replaced | `kubectl get pv dynamo-kv-models -o jsonpath='{.spec.csi.volumeHandle}'` must be your `fs-…` ID |
| Worker exits with a Hugging Face / repository error for `/models/Qwen3-8B` | The directory does not exist on the volume (download Job not finished or failed), so Dynamo treats the value as a Hub repo ID | `kubectl logs -n dynamo-system job/qwen3-8b-to-efs` must end with `DOWNLOAD_COMPLETE`; then delete the worker pods |
| `[lab] installing ai-dynamo` fails | No egress to PyPI from the nodes | Allow egress, or bake the image with `Dockerfile.dlc-dynamo` |
| Frontend `CrashLoopBackOff`: `model-path must be a valid directory` / tokenizer checksum mismatch | The volume is not mounted, the download is incomplete, or the files changed after the workers started | `kubectl exec -n dynamo-system <frontend> -- ls /models/Qwen3-8B`; restart workers and frontends together after re-downloading |
| Worker OOMKilled during load | Streamer buffer + vLLM exceed the pod limit | Lower `memory_limit` in `--model-loader-extra-config` (for example to 4 GiB) |
| `ValueError: ... max_model_len ... larger than the maximum number of tokens that can be stored in KV cache` | `--num-gpu-blocks-override` too small for `--max-model-len` | Keep blocks × 16 ≥ `--max-model-len` |
| KV router and round-robin give the same numbers | Working set fits in one GPU, or KV events not arriving | Confirm `--num-gpu-blocks-override` and `--kv-events-config` on the workers; increase `--tenants` or `--prefix-words` |
| KV router only slightly better; both repeat TTFTs in the hundreds of ms | Benchmark run from a laptop through `port-forward` (network time dominates TTFT); the router's overlap credit left at Dynamo's default 1.0 (load balancing overrides cache affinity); or prompts much longer than ~5,500 tokens (the working set overflows both caches) | Run the benchmark in-cluster (Step 7); `kubectl exec -n dynamo-system deploy/qwen3-8b-kv-frontend -- env \| grep OVERLAP` should show `4.0`; check `prompt length` in the output and lower `--prefix-words` if needed |
| `prefix-cache hit` lines missing from the benchmark output | `--worker-metrics` empty or the pod IPs changed after a worker restart | Re-run the `WORKER_METRICS=$(kubectl get pod …)` line from Step 7 before the benchmark |
| **Dynamo KV-Aware Routing (lab)** dashboard missing in Grafana | The dashboard ConfigMap was never applied | `kubectl get cm -n monitoring grafana-dashboard-dynamo-kv-routing`; if missing, `kubectl apply -f manifests/monitoring/kv-routing-dashboard.yaml`. The Grafana sidecar loads it within a minute |
| All DCGM panels empty, and Prometheus has no `dcgm-exporter` target | The ServiceMonitor was rejected: `scrapeTimeout` greater than `interval` | `kubectl logs -n monitoring deploy/kube-prometheus-stack-operator \| grep dcgm`; keep `serviceMonitor.scrapeTimeout: 10s` in `dcgm-exporter-values.yaml` and re-run the `helm upgrade --install` |
| DCGM DaemonSet `DESIRED 0` with GPU nodes up | Node label mismatch | `kubectl get nodes -L eks.amazonaws.com/instance-gpu-manufacturer` should show `nvidia` |
| DCGM `PROF_*` panels empty | Profiling fields unavailable | The standard fields (`GPU_UTIL`, `FB_USED`, `POWER_USAGE`) still work; check the dcgm-exporter logs for `Skipping line` |
| Dashboard Dynamo panels empty (GPU panels fine) | The chart's PodMonitors are missing (Dynamo installed before kube-prometheus-stack), or not picked up | `kubectl get podmonitor -n dynamo-system` should list `dynamo-frontend` and `dynamo-worker`; if not, re-run the Step 4 `helm upgrade --install` for `dynamo-platform` now that the CRDs exist. Prometheus UI → Status → Targets should list `podMonitor/dynamo-system/dynamo-frontend/0` and `podMonitor/dynamo-system/dynamo-worker/0` |

---

## Files in this lab

```text
dynamo-kv-routing/
├── index.md                                # this guide
├── Dockerfile.dlc-dynamo                   # optional: bake ai-dynamo into the vLLM DLC
├── scripts/
│   ├── dlc-dynamo-entrypoint.sh            # installs ai-dynamo 1.4.0 into the DLC, starts frontend/worker
│   └── kv_routing_bench.py                 # multi-tenant shared-prefix A/B benchmark (stdlib only)
└── manifests/
    ├── eksctl-cluster.yaml                 # EKS Auto Mode cluster
    ├── auto-ebs-sc.yaml                    # default gp3 StorageClass (NATS PVC)
    ├── gpu-nodepool.yaml                   # Auto Mode NodePool: up to 2x g6e.xlarge
    ├── efs-model-storage.yaml              # EFS StorageClass, PV, and the shared model-cache PVC
    ├── model-download-job.yaml             # Hugging Face -> EFS download of Qwen3-8B
    ├── qwen3-8b-kv-router.yaml             # DynamoGraphDeployment: 2 frontends (kv, round-robin) + 2 workers
    └── monitoring/
        ├── kube-prometheus-stack-values.yaml   # Prometheus + Grafana (+ DCGM dashboard 12239)
        ├── dcgm-exporter-values.yaml           # DCGM Exporter on Auto Mode GPU nodes
        └── kv-routing-dashboard.yaml           # Grafana: cache hit rate, TTFT, DCGM side by side
```

---

## References

- [NVIDIA Dynamo — KV-aware routing with the Dynamo frontend](https://docs.dynamo.nvidia.com/dynamo/kubernetes/kv-aware-routing/using-the-dynamo-frontend)
- [NVIDIA Dynamo — Router overview (v1.4.0)](https://docs.dynamo.nvidia.com/dynamo/v1.4.0/knowledge-base/modular-components/router/overview)
- [Dynamo `agg_router.yaml` example (v1.4.0)](https://github.com/ai-dynamo/dynamo/blob/v1.4.0/examples/backends/vllm/deploy/agg_router.yaml)
- [AWS Deep Learning Containers — vLLM](https://aws.github.io/deep-learning-containers/vllm/)
- [Amazon EKS — Load & serve models (vLLM DLC + Run:ai Model Streamer)](https://docs.aws.amazon.com/eks/latest/userguide/ml-inference-load-serve-model.html)
- [Amazon EKS — Accelerate model loading](https://docs.aws.amazon.com/eks/latest/userguide/ml-inference-fast-model-loading.html)
- [Amazon EKS — Use elastic file system storage with Amazon EFS](https://docs.aws.amazon.com/eks/latest/userguide/efs-csi.html)
- [NVIDIA Dynamo — Fast model weight loading (runai_streamer from a shared volume)](https://docs.nvidia.com/dynamo/kubernetes/model-deployment/model-loading/fast-model-loading)
- [Amazon EKS — AI/ML cluster setup (monitoring stack, DCGM Exporter)](https://docs.aws.amazon.com/eks/latest/userguide/ml-cluster-setup-cli.html)
- [GenAI on EKS workshop](https://catalog.workshops.aws/genai-on-eks/en-US) and [GenAI on EKS Starter Kit — Dynamo vLLM](https://aws-samples.github.io/sample-genai-on-eks-starter-kit/components/nvidia-platform/dynamo-vllm/)
- [NVIDIA DCGM Exporter](https://docs.nvidia.com/datacenter/cloud-native/gpu-telemetry/latest/dcgm-exporter.html) and [Grafana dashboard 12239](https://grafana.com/grafana/dashboards/12239)
- Related lab: [Disaggregated Inference (Dynamo)](../dynamo-disaggregated/index.md)
