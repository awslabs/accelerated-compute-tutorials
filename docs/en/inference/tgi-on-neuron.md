---
title: TGI on Neuron
description: Deploy Hugging Face TGI on AWS Neuron devices
tags:
  - inference
  - tgi
  - neuron
  - trainium
---

# TGI on Neuron

This tutorial walks you through running Hugging Face Text Generation Inference (TGI) on AWS Trainium.

---

## Overview

[TGI](https://huggingface.co/docs/text-generation-inference/) is a production-grade LLM inference server from Hugging Face. It supports the AWS Neuron backend for native execution on Trainium.

### vLLM vs TGI

| Feature | vLLM | TGI |
|---------|------|-----|
| Continuous Batching | ✅ | ✅ |
| Neuron Support | ✅ | ✅ |
| HF Hub Integration | Partial | Full |
| Production Stability | High | High |
| Docker Image | Self-build | HF Official |

---

## Prerequisites

- AWS account with `trn1` instance access
- Docker installed
- Hugging Face account and token (for gated models)

---

## Step 1: Prepare Docker Image

```bash
# Pull official HF TGI Neuron image
docker pull ghcr.io/huggingface/neuronx-tgi:latest
```

---

## Step 2: Serve Model

```bash
# Run TGI server (Llama 3.1 8B)
docker run -d --name tgi-neuron \
  --device=/dev/neuron0 \
  -p 8080:80 \
  -e HF_TOKEN=$HF_TOKEN \
  -e MAX_INPUT_LENGTH=2048 \
  -e MAX_TOTAL_TOKENS=4096 \
  ghcr.io/huggingface/neuronx-tgi:latest \
  --model-id meta-llama/Meta-Llama-3.1-8B-Instruct \
  --num-shard 2
```

---

## Step 3: Test

```bash
# Health check
curl http://localhost:8080/health

# Inference request
curl http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": "What are the benefits of AWS Trainium?",
    "parameters": {
      "max_new_tokens": 100,
      "temperature": 0.7
    }
  }'
```

---

## Clean Up

```bash
docker stop tgi-neuron && docker rm tgi-neuron
```

---

## References

- [TGI on AWS Neuron Official Docs](https://huggingface.co/docs/text-generation-inference/backends/neuron)
- [Optimum Neuron](https://huggingface.co/docs/optimum-neuron/)
