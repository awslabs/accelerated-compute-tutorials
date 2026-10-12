# vLLM Production Monitoring & Scaling

| Environment | EKS + vLLM + Grafana/Prometheus + DCGM Exporter |
| --- | --- |
| Reference docs | [AWS EKS official: Identify scaling metric thresholds](https://docs.aws.amazon.com/eks/latest/userguide/ml-inference-autoscaling-thresholds.html) |

## 1. Traditional ML vs. LLM monitoring — why is it different?

If you have experience operating traditional ML (classification/regression/detection models), you can understand the differences in LLM monitoring using the comparison table below.

| Category | Traditional ML (classification/regression/detection) | LLM inference (vLLM) |
| --- | --- | --- |
| **Key metrics** | Latency, Throughput, Error Rate, Accuracy | + **TTFT, TPOT, KV Cache utilization, Queue Depth** |
| **Bottleneck resource** | CPU / Memory | **GPU VRAM + Memory Bandwidth** (CPU is almost irrelevant) |
| **Scaling signal** | CPU > 70% or rising latency | **Queue Depth spike** (CPU/Memory can't be used as a reference) |
| **Response structure** | Request → immediate response (a few ms) | Request → **streaming token generation** (seconds to tens of seconds) |
| **Cost unit** | Per request | **Per token** (input + output tokens) |
| **Memory characteristics** | Fixed (constant after model load) | **Variable** (KV Cache is dynamically allocated/freed per request) |
| **Batching** | Static batching (fixed batch size) | **Continuous Batching** (dynamic join/leave) |
| **Cold Start** | Model load takes a few seconds | Model load takes **2-10 minutes** + CUDA warmup required |
| **OOM pattern** | Rare (memory is predictable) | **Frequent** (KV Cache balloons with long prompts/concurrent requests) |
| **GPU utilization interpretation** | Higher is better | 30-50% is also normal (memory-bound workload) |

### Why is it different?

```
[Traditional ML]
  Input → [Model (fixed)] → Output
  - Constant compute, constant memory, predictable response time

[LLM inference]
  Input (variable length) → [Prefill: process the entire input] → first token (TTFT)
                   → [Decode: generate one token at a time] → ... → done
  - Compute = proportional to input length × output length
  - KV Cache = dynamically allocated per request (long input = memory spike)
  - Concurrent requests = KV Cache contention → OOM or preemption

```

### Dashboard operations summary

| What you watched in traditional ML | Replaced in LLM with this |
| --- | --- |
| CPU utilization → scaling decision | ❌ Meaningless → decide by **Queue Depth** |
| Response Time (single value) | Need to separate **TTFT + TPOT** (different UX impact) |
| Memory utilization | **KV Cache utilization** (general memory is reference only) |
| Error Rate | Still valid + add **Preemption Count** |
| Model Accuracy | Needs a separate evaluation pipeline in production (offline) |

## 2. Monitoring architecture

```
Prometheus (kube-prometheus-stack)
  ├── vLLM /metrics (ServiceMonitor)
  ├── DCGM Exporter (GPU metrics)
  └── Node Exporter (CPU/Mem)
        ↓ Remote Write (at production scale)
Amazon Managed Prometheus (AMP)
        ↓
Grafana (or Amazon Managed Grafana)
  ├── vLLM dashboard
  ├── GPU dashboard (DCGM)
  └── Kubernetes dashboard
        ↓
KEDA ScaledObject
  ├── Queue depth trigger
  └── P95 latency trigger (SLO guardrail)
        ↓
Karpenter NodePool (auto-provisions GPU nodes)

```

## 3. Core monitoring metrics — a 3-tier system

### 🔴 Tier 1 — LLM service quality (user-facing SLI)

| Metric (Prometheus metric) | Meaning | Grafana panel | Normal range |
| --- | --- | --- | --- |
| `vllm:e2e_request_latency_seconds` | **E2E request latency** (P50/P95/P99) | Time series | < SLO (varies by model/use case) |
| `vllm:time_to_first_token_seconds` | **TTFT** — time to the first token. Directly tied to UX | Time series | < 1-3 s (depends on input length) |
| `vllm:time_per_output_token_seconds` | **TPOT** — token generation speed | Gauge | 30-100 ms (depends on model size/TP) |
| `vllm:num_requests_waiting` | **Waiting queue depth** — the primary scale-out signal | Stat + Alert | 0-5 |
| `vllm:num_requests_running` | Number of requests currently processing | Stat | Depends on model/GPU |
| `vllm:request_success_total` | Number of successful requests (for rate calculation) | Time series | Error rate < 1% |

### 🟡 Tier 2 — vLLM internal state (performance tuning)

| Metric | Meaning | Attention threshold |
| --- | --- | --- |
| `vllm:gpu_cache_usage_perc` | **KV Cache occupancy** | Alert at > 80%, respond immediately at > 95% |
| `vllm:num_preemptions_total` | Number of preemptions | A spike signals GPU memory shortage |
| `vllm:prompt_tokens_total` / `generation_tokens_total` | Input/output token throughput | For capacity planning |
| `vllm:iteration_tokens_total` | Tokens per batch iteration | For analyzing batch efficiency |

### 🟢 Tier 3 — GPU / infrastructure (node level)

| Metric (DCGM) | Meaning |
| --- | --- |
| `DCGM_FI_DEV_GPU_UTIL` | GPU compute utilization |
| `DCGM_FI_DEV_MEM_COPY_UTIL` | GPU memory bandwidth |
| `DCGM_FI_DEV_FB_USED` / `FB_FREE` | GPU VRAM used/free |
| `DCGM_FI_DEV_POWER_USAGE` | Power usage (cost tracking) |
| `DCGM_FI_DEV_ECC_SBE_VOL_TOTAL` | GPU ECC errors (hardware fault detection) |
| `container_cpu_usage_seconds_total` | Pod CPU utilization |
| `container_memory_working_set_bytes` | Pod memory |

!!! info "A note on interpreting GPU Util"
    vLLM continuous batching is a memory-bound workload — a GPU compute utilization of 30-50% is still normal. The "higher utilization is better" interpretation used for CPUs does not apply.

## 4. Scale-out thresholds — the official AWS methodology

> 📎 **Source:** [AWS EKS official docs — Identify scaling metric thresholds for AI inference](https://docs.aws.amazon.com/eks/latest/userguide/ml-inference-autoscaling-thresholds.html)

### 4-1. How to derive thresholds (k6 load testing)

```
1. Warmup: 100 sequential requests (CUDA graph capture, kernel compilation complete)
2. Apply gradual load across 10 → 20 → 30 → 40 → 50 → 60 → 70 RPS steps
   - Hold each step for 60 s, rest 30 s between steps
3. Observe simultaneously in Grafana:
   - vllm:num_requests_waiting (queue depth)
   - vllm:e2e_request_latency_seconds (latency)
4. The RPS point where queue depth suddenly spikes from near 0 = saturation point
5. Set the value just before the saturation point as the scale-out threshold

```

### 4-2. Scale-out triggers

| Trigger | Threshold (example) | Meaning | Notes |
| --- | --- | --- | --- |
| **Queue depth (primary)** | `vllm:num_requests_waiting > N` (per pod) | When waiting requests exceed the limit | demand signal — measure N empirically with k6 |
| **P95 latency (secondary, SLO guardrail)** | `p95(e2e_latency) > SLO` | Scale preemptively just before an SLO violation | Effective for long prompts/image inputs |

!!! warning "Always measure thresholds against your own workload"
    The example values above are based on the small model (Ministral-3B + g6e.4xlarge) from the AWS documentation. The saturation point varies greatly with model size, GPU type, and input patterns, so you **must** verify it with your own k6 load test.

### 4-3. Scale-in conditions

| Condition | Setting |
| --- | --- |
| Queue == 0 + Latency < SLO/2 | Scale in when sustained for 5+ minutes |
| `stabilizationWindowSeconds` | **300 s or more** (GPU Pods start slowly — model loading takes 2-10 minutes) |
| Pods removed at once | Max 1 per 2 minutes (conservative) |

## 5. KEDA ScaledObject configuration (example)

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: vllm-inference-app
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: vllm-inference-app
  minReplicaCount: 1
  maxReplicaCount: 5
  advanced:
    horizontalPodAutoscalerConfig:
      behavior:
        scaleUp:
          stabilizationWindowSeconds: 30   # fast scale up
          policies:
            - type: Pods
              value: 2
              periodSeconds: 60
        scaleDown:
          stabilizationWindowSeconds: 300  # conservative scale down
          policies:
            - type: Pods
              value: 1
              periodSeconds: 120
  triggers:
    # Primary: queue depth (demand signal)
    - type: prometheus
      metricType: AverageValue
      metadata:
        serverAddress: http://kube-prometheus-stack-prometheus.monitoring.svc:9090
        query: sum(vllm:num_requests_waiting) or vector(0)
        threshold: "25"          # ← adjust after measuring with k6
        activationThreshold: "1"
    # Secondary: P95 latency (SLO guardrail)
    - type: prometheus
      metricType: AverageValue
      metadata:
        serverAddress: http://kube-prometheus-stack-prometheus.monitoring.svc:9090
        query: histogram_quantile(0.95, sum(rate(vllm:e2e_request_latency_seconds_bucket[1m])) by (le)) or vector(0)
        threshold: "5"           # ← adjust to your SLO

```

**Why use KEDA:** Compared to HPA, it integrates directly with Prometheus queries and supports an activation threshold (ignoring spikes).

**Node scaling:** When a Pending pod appears, Karpenter automatically provisions a GPU node → a **two-tier structure** of Pod scale-out plus automatic GPU node addition.

- [AWS official: Autoscale AI inference with HPA and KEDA](https://docs.aws.amazon.com/eks/latest/userguide/ml-inference-autoscaling-hpa-keda.html)

## 6. Alert Rules

| Alert | Condition | Severity | Meaning |
| --- | --- | --- | --- |
| VLLMHighQueueDepth | `num_requests_waiting > 50` for 2 min | ⚠️ warning | Scaling delay or load exceeded |
| VLLMHighLatency | `p95(e2e_latency) > SLO` for 2 min | 🔴 critical | SLO violation |
| VLLMGPUMemoryCritical | `FB_USED/FB_TOTAL > 95%` for 1 min | 🔴 critical | OOM imminent |
| VLLMKVCacheFull | `gpu_cache_usage_perc > 95%` for 30 s | 🔴 critical | Preemption/OOM imminent |
| VLLMPreemptionSpike | `rate(preemptions[5m]) > 5` | ⚠️ warning | Requests interrupted due to memory shortage |

## 7. Production double-check points

Checks before opening the system to traffic after deployment:

| # | Item | Check |
| --- | --- | --- |
| 1 | Verify the vLLM `/metrics` endpoint is exposed |  |
| 2 | Verify ServiceMonitor → Prometheus scraping |  |
| 3 | Verify the DCGM Exporter DaemonSet is running |  |
| 4 | Configure Grafana dashboards (Tier 1/2/3 metrics) |  |
| 5 | Register alert rules (5) |  |
| 6 | Install KEDA & apply ScaledObject |  |
| 7 | Apply the Karpenter `do-not-disrupt` annotation |  |
| 8 | **k6 load test — confirm the saturation point** |  |
| 9 | Auto-run the warmup script (100 runs) after deployment |  |
| 10 | Optimize `gpu_memory_utilization` / `max_model_len` |  |
| 11 | Verify the Scale Out → Scale In cycle |  |

### Commonly missed items

!!! tip "KV Cache settings"
    `gpu_memory_utilization=0.85` is recommended (default 0.9 — too high causes OOM). Setting a `vllm:gpu_cache_usage_perc > 80%` alert is essential.

!!! tip "Protecting against Karpenter consolidation"
    `yaml # Add an annotation to the vLLM Pod (Deployment template) metadata: annotations: karpenter.sh/do-not-disrupt: "true" ` Without this, Karpenter may **interrupt serving** while performing node consolidation.

!!! tip "GPU warmup"
    The first requests are several times slower due to CUDA graph capture and kernel compilation. We recommend **pre-processing 100 warmup requests** before the health check after deployment. Configure the ReadinessProbe to pass only after warmup completes.

!!! tip "Reviewing max_model_len"
    The default (the model's maximum supported) → can over-occupy KV Cache memory. Adjust it to the maximum context length you actually use (e.g., 65,536) → increases concurrent throughput.

## 8. Reference resources

| Resource | Description |
| --- | --- |
| [AWS EKS: Identify scaling metric thresholds](https://docs.aws.amazon.com/eks/latest/userguide/ml-inference-autoscaling-thresholds.html) | k6 load testing → threshold derivation → KEDA configuration (end-to-end) |
| [AWS EKS: Autoscale AI inference with HPA and KEDA](https://docs.aws.amazon.com/eks/latest/userguide/ml-inference-autoscaling-hpa-keda.html) | Detailed KEDA ScaledObject configuration |
| [EKS Best Practices: AI/ML](https://docs.aws.amazon.com/eks/latest/best-practices/aiml.html) | Best practices for the overall architecture |
| [Workshop: Generative AI on EKS (NVIDIA GPU)](https://catalog.us-east-1.prod.workshops.aws/workshops/029d6c4e-4775-41c9-85ff-9f5360f32a15/en-US) | Hands-on vLLM deployment + ServiceMonitor + Grafana dashboards |
| [Workshop: Scaling LLM Inference with vLLM](https://catalog.us-east-1.prod.workshops.aws/workshops/177cf2c8-d451-405b-a463-eb77d38b8617/en-US/vllm/observability) | Provides vLLM dashboard JSON directly, includes Prometheus queries |
| [awslabs/ai-ml-observability-reference-architecture](https://github.com/awslabs/ai-ml-observability-reference-architecture) | Integrated RA of Prometheus + Grafana + OpenSearch |
| [awslabs/ai-on-eks](https://github.com/awslabs/ai-on-eks) | All AI on EKS resources |
