---
title: vLLM on Neuron
description: Serve LLMs at high performance on AWS Trainium using vLLM
tags:
  - inference
  - vllm
  - neuron
  - trainium
---

# vLLM on Neuron

This tutorial walks you through running the vLLM framework on AWS Trainium to serve large language models at high speed.

---

## Overview

[vLLM](https://docs.vllm.ai/) is a high-performance LLM inference engine based on PagedAttention.
It integrates with the AWS Neuron SDK to run natively on Trainium.

### Key Features

- **Continuous Batching**: Maximize throughput with dynamic batching
- **PagedAttention**: Memory-efficient KV cache management
- **Tensor Parallelism**: Distribute models across multiple NeuronCores
- **OpenAI-compatible API**: Drop-in replacement for existing applications

---

## Prerequisites

- AWS account with access to `trn1.32xlarge` or larger instances
- Tools installed from the [Getting Started](../getting-started.md) guide
- Docker installed

---

## Step 1: Environment Setup

```bash
# Launch EC2 instance with Neuron Deep Learning AMI
aws ec2 run-instances \
  --image-id ami-0xxxxxxxxxxxxx \
  --instance-type trn1.32xlarge \
  --key-name my-key \
  --security-group-ids sg-xxxxxxxx
```

!!! tip "AMI Selection"
    Use the latest `Deep Learning AMI Neuron (Ubuntu 22.04)`.
    Neuron drivers and runtime are pre-installed.

---

## Step 2: Install vLLM

```bash
# Create virtual environment
python -m venv vllm-env
source vllm-env/bin/activate

# Install vLLM (Neuron build)
pip install vllm[neuron]
```

---

## Step 3: Compile Model

Models must be compiled to Neuron format for execution on Neuron devices:

```bash
# Compile Llama 3.1 8B model
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Meta-Llama-3.1-8B-Instruct \
  --device neuron \
  --tensor-parallel-size 2 \
  --max-model-len 4096 \
  --block-size 4096
```

!!! warning "Compilation Time"
    First-time compilation may take 15-30 minutes.
    Compiled models are cached for faster subsequent loads.

---

## Step 4: Run Inference Server

```bash
# Launch OpenAI-compatible API server
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Meta-Llama-3.1-8B-Instruct \
  --device neuron \
  --tensor-parallel-size 2 \
  --port 8000
```

---

## Step 5: Test

```bash
# Send inference request with curl
curl http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "prompt": "The benefits of AWS Trainium are",
    "max_tokens": 100,
    "temperature": 0.7
  }'
```

---

## Performance Benchmarks

| Model | Instance | TP | Throughput | Latency (P50) |
|-------|---------|-----|-----------|---------------|
| Llama 3.1 8B | trn1.2xlarge | 2 | ~800 tok/s | ~35ms |
| Llama 3.1 70B | trn1.32xlarge | 32 | ~400 tok/s | ~80ms |

---

## Clean Up

```bash
# Terminate EC2 instance
aws ec2 terminate-instances --instance-ids i-xxxxxxxxxxxxxxxxx
```

!!! danger "Cost Prevention"
    Always terminate unused trn1 instances.
    trn1.32xlarge costs approximately $21.50/hour (On-Demand).

---

## References

- [vLLM Official Docs - Neuron](https://docs.vllm.ai/en/latest/getting_started/neuron-installation.html)
- [AWS Neuron SDK Documentation](https://awsdocs-neuron.readthedocs-hosted.com/)
- [Trainium Instance Pricing](https://aws.amazon.com/ec2/pricing/on-demand/)
