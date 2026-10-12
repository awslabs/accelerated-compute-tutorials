---
title: AI Infrastructure Decision Guide
description: A technical review framework for deciding where to run AI — across Bedrock, SageMaker, EKS, EC2, and ParallelCluster — based on workload characteristics
tags:
  - AI Infrastructure
  - FlexAI
  - Decision Making
  - Bedrock
  - SageMaker
  - EKS
---

# AI Infrastructure Decision Guide

**"Where should you run AI?"** — This guide provides a technical review framework spanning workload analysis → constraint check → infrastructure matching.

## What is Flexible AI (FlexAI)?

Flexible AI (FlexAI) is **a methodology and reference architecture for building a self-managed AI platform on AWS**. It is not tied to a specific orchestrator (EKS, ParallelCluster, SLURM); instead, it aims to flexibly combine Managed (Bedrock, SageMaker) and Self-Managed options according to workload characteristics.

**Core principle:** Avoid lock-in to any single service and secure the flexibility to choose the optimal operating environment for each workload. Workloads where a Bedrock API call is optimal go to Bedrock; workloads that need GPU control go to EKS/EC2; large-scale distributed training goes to ParallelCluster — **the decision criteria for placing each in the right place** are the purpose of this guide.

## Prerequisites

This guide starts from a state where **the model has already been decided**. "Which model should we use?" is a separate review area; here we focus on **where and how to run that model**.

!!! info "There is no single right answer"
    Most production environments are **hybrid**. Starting with Bedrock but moving only some workloads to Self-Managed is the most common pattern. This guide helps you make decisions **per workload**.

## 1. Quick decision — a 3-minute decision flow

```
Q1. Is an API call alone enough?
    (No model customization needed, solvable with prompt engineering only)
    ├── Yes → Bedrock (serverless)
    └── No ↓

Q2. Do you need fine-tuning?
    ├── Bedrock-supported model + simple SFT → Bedrock Custom Model
    ├── SageMaker-supported model + want managed → SageMaker
    └── Open-source model / custom training pipeline → Self-Managed (EKS or EC2) ↓

Q3. Do you need token-economics optimization?
    (Per-model cost control, GPU utilization optimization, batching/caching strategies)
    ├── Yes → Self-Managed confirmed (not possible on Bedrock/SageMaker)
    └── No → to Q4 ↓

Q4. Is API throttling a problem?
    (Bedrock concurrent-request limits, SageMaker endpoint limits)
    ├── Yes → Self-Managed confirmed
    └── No → Managed (Bedrock or SageMaker)

```

## 2. Detailed review — mapping by workload characteristics

### 2-1. Inference workloads

| Characteristic | Bedrock | SageMaker Endpoint | EKS + vLLM | EC2 standalone |
| --- | --- | --- | --- | --- |
| API call only (no customization) | ⭐ | ✅ | ⚠️ unnecessary complexity | ❌ |
| Prompt engineering | ⭐ | ✅ | ✅ | ✅ |
| Model selection breadth (incl. open source) | Limited | Wide | ⭐ Unlimited | ⭐ Unlimited |
| Token economics (per-model cost) | ❌ | Limited | ⭐ | ⭐ |
| Continuous Batching | ❌ no control | Limited | ⭐ | ⭐ |
| KV Cache control | ❌ | ❌ | ⭐ | ⭐ |
| GPU utilization optimization | ❌ | Limited | ⭐ | ⭐ |
| Autoscaling | ✅ automatic | ✅ | ✅ (KEDA) | ❌ manual |
| Operational burden | ⭐ none | Low | Medium | High |
| Cost predictability | Token pay-per-use | Instance hours | Instance hours | Instance hours |

### 2-2. Training workloads

!!! tip "Training mostly starts on EC2 or ParallelCluster"
    Introducing EKS for training workloads makes sense only **from the point where you need orchestration**. For single-model experiments or PoCs, EC2 standalone is the fastest, and for large-scale distributed training, SLURM-based ParallelCluster is the mature choice. EKS is valuable when you need **multi-team GPU sharing or an integrated training-serving pipeline**.

| Characteristic | EC2 standalone | ParallelCluster (SLURM) | EKS + Kubeflow | SageMaker Training |
| --- | --- | --- | --- | --- |
| **PoC / experiment** | ⭐ optimal (`python train.py`) | ⚠️ unnecessary complexity | ❌ unnecessary complexity | ✅ |
| **Large-scale distributed training** (Multi-Node) | ❌ manual management | ⭐ SLURM native | ✅ (torchrun + Job) | ✅ |
| **SLURM job scheduling** | ❌ | ⭐ native | ❌ (K8s scheduler) | ❌ |
| **Multi-team GPU sharing** | ❌ | ✅ (SLURM partition) | ⭐ (Kueue quota) | ✅ |
| **Training→serving integrated pipeline** | ❌ | ❌ | ⭐ (KFP→KServe) | ✅ (SageMaker Pipelines) |
| **Spot instance usage** | ✅ (manual) | ✅ | ✅ (Karpenter) | ✅ |
| **HPC integration (MPI, NCCL optimization)** | ✅ (manual) | ⭐ (EFA native) | ✅ | ✅ |
| **Open source / portability** | ⭐ | ⭐ | ⭐ | ❌ (AWS lock-in) |
| **Operational burden** | High | Medium | Medium-High | Low |
| **K8s expertise required** | ❌ | ❌ | ✅ required | ❌ |

**Why EKS may not be a good fit for training:**

| # | Rationale | Explanation |
| --- | --- | --- |
| 1 | **K8s abstraction cost > benefit** | A single-GPU job is done with `python train.py`. Writing K8s Deployment/Job YAML + PVC + GPU scheduling setup takes longer than the actual training time |
| 2 | **SLURM is more mature for training** | Distributed training (torchrun, DeepSpeed) has been optimized on SLURM for decades. Multi-node runs with a single sbatch line. On K8s, Job/MPIOperator setup is complex |
| 3 | **GPU node startup time** | Starting a GPU Pod on EKS = Karpenter node provisioning (2-5 min) + container image pull (several min) + GPU driver initialization. ParallelCluster keeps nodes allocated at all times, so it starts without delay |
| 4 | **Checkpoint/restart** | In SLURM, job arrays, dependencies, and requeue are native. On K8s, they require separate implementation |
| 5 | **Frequent experiment iteration** | Change a hyperparameter → rerun `python train.py` immediately vs. submitting a KFP Job — a 10x difference in iteration speed |

**When EKS shines for training:**

| Scenario | Reason |
| --- | --- |
| **Unified inference + training platform** | When you want to put training on the serving EKS cluster and manage everything as a single infrastructure |
| **Multi-team GPU sharing** (10+ teams) | Kueue quotas + namespace separation are more flexible than SLURM partitions |
| **CI/CD-integrated automatic retraining** | When an automated KFP → MLflow → KServe pipeline is valuable |

### 2-3. Agent / RAG workloads

| Characteristic | Bedrock Agents | EKS + LangGraph/Strands | EC2 standalone |
| --- | --- | --- | --- |
| Managed agents | ⭐ | ❌ | ❌ |
| Custom orchestration | Limited | ⭐ | ⭐ |
| Tool/MCP integration | Bedrock Actions | ⭐ Unlimited | ⭐ Unlimited |
| Knowledge Base (RAG) | Bedrock KB | Build it yourself | Build it yourself |
| Multi-model routing | ❌ | ⭐ (LiteLLM/AI Gateway) | Possible |
| Cost control | Token pay-per-use | ⭐ Fine-grained | ⭐ Fine-grained |

## 3. Key decision points — a weighted scoring system

!!! tip "The higher the score, the more it points to Self-Managed"
    7 or more strongly recommends Self-Managed. 4-6 suggests considering hybrid. 3 or below means Managed is sufficient.

| # | Condition | Weight | Applies |
| --- | --- | --- | --- |
| 1 | Token-economics optimization needed (per-model cost, batching, caching) | **+3** | ☐ |
| 2 | Need to avoid API throttling (hundreds to thousands of concurrent requests) | **+3** | ☐ |
| 3 | Open-source model required (model not supported by Bedrock) | +2 | ☐ |
| 4 | Need direct control over GPU type/quantity | +2 | ☐ |
| 5 | On-premises/hybrid requirement (EKS Hybrid Nodes) | +2 | ☐ |
| 6 | Multi-model routing / A-B testing needed | +2 | ☐ |
| 7 | Custom serving pipeline (vLLM parameter tuning, etc.) | +1 | ☐ |
| 8 | Existing Kubernetes infrastructure | +1 | ☐ |
| 9 | Data sovereignty/security regulations (cloud API call restrictions) | +1 | ☐ |

!!! warning "If even one +3 condition applies"
    If the token-economics or API-throttle condition applies, **it is structurally impossible with Bedrock/SageMaker serverless**. Self-Managed is required.

| Score range | Recommendation |
| --- | --- |
| **0-3 points** | **Bedrock** (or SageMaker) — Managed is sufficient |
| **4-6 points** | **Hybrid** — Bedrock by default + only specific workloads Self-Managed |
| **7+ points** | **Self-Managed** (EKS-based FlexAI) recommended |

## 4. When choosing Self-Managed — EKS for inference, training depends on the situation

If you've decided on Self-Managed, **the orchestrator differs by workload type**:

```
[Inference]
Q5. Multi-model serving + autoscaling?
    ├── Yes → EKS + vLLM + Karpenter/KEDA
    └── No (single-model PoC) → EC2 standalone

[Training]
Q6. What scale of training?
    ├── PoC / single-GPU experiment → EC2 standalone (minimal initial setup cost)
    ├── Large-scale distributed training (Multi-Node) → ParallelCluster (SLURM)
    └── Integrated with the inference cluster → EKS + KFP (but requires K8s expertise)

[Hybrid]
Q7. On-premises integration?
    ├── Yes → EKS Hybrid Nodes
    └── No → standard configuration

```

### Recommended orchestrator by workload

| Workload | 1st choice | 2nd choice | Notes |
| --- | --- | --- | --- |
| **Inference serving** (production) | EKS | EC2 (single model) | EKS's core strength area |
| **PoC / experiment** | EC2 | — | Can start immediately with `python train.py` |
| **Large-scale distributed training** | ParallelCluster | EKS | SLURM is more mature for distributed training |
| **Scheduled retraining pipeline** | EKS (KFP) | SageMaker | When integrated with inference |
| **HPC workloads** (pre-training) | ParallelCluster | — | EFA + SLURM native |
| **Multi-team resource sharing** | EKS (Kueue) | ParallelCluster (partition) | EKS is advantageous with 10+ teams |

### EC2 vs ParallelCluster vs EKS comparison

| Criterion | EC2 standalone | ParallelCluster (SLURM) | EKS |
| --- | --- | --- | --- |
| **Core strength** | Simple setup, instant start | Large-scale distributed training, HPC | Inference serving, microservice orchestration |
| **Training suitability** | ⭐ PoC | ⭐ Distributed training | ⚠️ Only when integration is needed |
| **Inference suitability** | ⚠️ Single model only | ❌ No serving support | ⭐ Core |
| **Scaling** | ❌ Manual | ✅ SLURM auto | ✅ Karpenter/KEDA |
| **K8s required** | ❌ | ❌ | ✅ Required |
| **Operational burden** | High | Medium | Medium |
| **Typical starting path** | PoC → migrate after validation | Training only | Inference only → add training |

## 5. Accelerator selection

After choosing Self-Managed (EKS/EC2), the next question is **which GPU/accelerator to use:**

→ See **[Accelerator Selection Guide](../gpu-selection-guide/)**

Summary:

| Workload | Recommended instance | Reason |
| --- | --- | --- |
| Large-scale training (>70B) | P5/P5en (H100/H200) | NVLink, bandwidth |
| Inference (7B-70B) | G6e (L40S) / G7e (RTX PRO 6000) | Cost efficiency + sufficient VRAM |
| Inference (< 7B) | G6 (L4) / Inf2 | Low cost |
| Cost-optimized training | Trn2 (Trainium) | 30-50% cheaper than P5 |

## 6. Hybrid architecture — the most common pattern

!!! success "Most production is hybrid"
    "All Bedrock" or "all EKS" is rare, because the optimal infrastructure differs per workload.

### Pattern A: Bedrock by default + only specific models Self-Managed

```
[Agent/RAG] → Bedrock (Claude, Titan, etc.)
[Core inference] → EKS + vLLM (open-source models, token-economics optimization)
[Training] → EC2 Spot (cost optimization)

```

**Best fit:** Mostly API calls, but you need cost/performance optimization for specific models

### Pattern B: EKS-centric + Bedrock as a complement

```
[All serving] → EKS + vLLM/LiteLLM (AI Gateway)
  ├── Open-source models → EKS GPU nodes
  └── Bedrock models → LiteLLM → Bedrock API (fallback/comparison)
[Training pipeline] → EKS + Kubeflow
[Observability] → Prometheus + Grafana + Langfuse

```

**Best fit:** Self-Managed-centric but you also want to use Bedrock models

### Pattern C: On-premises + cloud hybrid

```
[Control plane] → EKS (cloud)
[Inference workers] → EKS Hybrid Nodes (on-premises GPUs)
[Training] → cloud GPUs (Spot/CB)
[Data] → on-premises (regulatory requirements)

```

**Best fit:** Data sovereignty regulations, leveraging existing on-premises GPU assets

## 7. Decision summary table

| Workload | Easiest starting point | Scale-up path |
| --- | --- | --- |
| LLM inference (API only) | **Bedrock** | → EKS + vLLM as costs rise |
| LLM inference (customization needed) | **EKS + vLLM** | → LiteLLM Gateway when adding models |
| Fine-tuning (simple) | **Bedrock Custom Model** | → EC2 → EKS + KFP when it gets complex |
| Fine-tuning (serious) | **EC2 standalone** (PoC) | → EKS + Kubeflow when it becomes routine |
| Agent/RAG | **Bedrock Agents** | → EKS + LangGraph when customizing |
| Image/vision inference | **EKS + vLLM** | → separate lightweight models onto CPU Pods |
| Embeddings | **Bedrock (Titan)** | → EKS + your own model at high volume |

## 8. Checklist

Questions to confirm in the first meeting:

| # | Question | Direction based on the answer |
| --- | --- | --- |
| 1 | What is the current AI workload? (inference/training/agent) | Identify the workload type |
| 2 | Which model are you using or evaluating? | Check Bedrock support |
| 3 | What is the expected traffic? (QPS, concurrent requests) | Assess throttling issues |
| 4 | Is cost optimization important? To what level? | Whether token economics is needed |
| 5 | Do you have Kubernetes operations experience? | Feasibility of adopting EKS |
| 6 | What are the data security/regulatory requirements? | Whether on-premises/hybrid is needed |
| 7 | Do you have existing GPU infrastructure? | Consider Hybrid Nodes |
| 8 | What level of management burden is acceptable? (staffing, operations) | Managed vs Self-Managed direction |

## References

- [Accelerator Selection Guide](../gpu-selection-guide/) — GPU/instance matching after deciding on Self-Managed
- [EKS Best Practices: AI/ML](https://docs.aws.amazon.com/eks/latest/best-practices/aiml.html) — Best practices for AI workloads on EKS
