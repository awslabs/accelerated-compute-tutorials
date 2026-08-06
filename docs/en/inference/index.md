---
title: Inference Infrastructure
description: Tutorials for serving large language models with high performance on AWS accelerated computing
---

# Inference Infrastructure

Hands-on tutorials for serving large language models (LLMs) with high performance and low cost on AWS Trainium and GPUs.

---

<div class="grid cards" markdown>

-   :material-lightning-bolt:{ .lg .middle } **vLLM on Neuron**

    ---

    Serve LLMs at high speed on Neuron using the vLLM framework

    [:octicons-arrow-right-24: View Tutorial](vllm-on-neuron.md)

-   :material-server:{ .lg .middle } **TGI on Neuron**

    ---

    Deploy Hugging Face Text Generation Inference on Neuron devices

    [:octicons-arrow-right-24: View Tutorial](tgi-on-neuron.md)

</div>

---

## Architecture Overview

```mermaid
graph TD
    A[Client Request] --> B[Load Balancer]
    B --> C[Inference Server]
    C --> D{Framework}
    D --> E[vLLM]
    D --> F[TGI]
    E --> G[Neuron Runtime]
    F --> G
    G --> H[Trainium]
```

---

## Supported Models

| Model Family | Parameters | Recommended Instance | Framework |
|-------------|-----------|---------------------|-----------|
| DBRX | 132B | trn1.32xlarge | vLLM |

!!! info "Model Support"
    Neuron SDK model support is continuously expanding.
    Check the latest supported models at [Neuron Model Hub](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/general/models/inference-models.html).
