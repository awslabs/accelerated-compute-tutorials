---
title: Training Infrastructure
description: Build large-scale distributed training pipelines with AWS Trainium
---

# Training Infrastructure

Tutorials for efficiently training large models using AWS Trainium and GPUs.

---

<div class="grid cards" markdown>

-   :material-lan:{ .lg .middle } **Distributed Training**

    ---

    Configure data-parallel and model-parallel distributed training across multiple Trainium nodes

    [:octicons-arrow-right-24: View Tutorial](distributed-training.md)

-   :material-language-python:{ .lg .middle } **PyTorch Native**

    ---

    Build Neuron-native training pipelines using PyTorch XLA

    [:octicons-arrow-right-24: View Tutorial](pytorch-native.md)

-   :material-hexagon-multiple:{ .lg .middle } **Distributed Fine-tuning & Inference with Ray + EFA**

    ---

    Run KubeRay on EKS across 2× p5.48xlarge (16× H100 GPUs) from an EC2 Capacity Block, with distributed LoRA fine-tuning (Qwen3-4B) and pipeline+tensor-parallel LLM inference (Qwen3-32B, TP=8 x PP=2) — cross-node NCCL running over EFA via a custom aws-ofi-nccl image on EKS Auto Mode

    [:octicons-arrow-right-24: View Lab Guide](ray-on-eks-efa/README.md)

</div>

---

## Training Strategy Comparison

| Strategy | Description | Use Case |
|----------|------------|----------|
| Data Parallelism (DP) | Replicate model across devices | Small/medium models |
| Tensor Parallelism (TP) | Split within layers | Large models |
| Pipeline Parallelism (PP) | Distribute layers across devices | Extra-large models |
| ZeRO / FSDP | Distribute optimizer state | Memory reduction |

---

## Supported Frameworks

- **Neuron Distributed** (neuronx-distributed)
- **PyTorch XLA** (torch-neuronx)
- **AWS Neuron NeMo Megatron**
- **Hugging Face Optimum Neuron**
