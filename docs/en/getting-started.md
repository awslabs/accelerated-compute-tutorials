---
title: Getting Started
description: Set up your development environment and prepare for your first tutorial
---

# Getting Started

This guide walks you through setting up the basic environment needed to follow the AI Infra on AWS Guide.

---

## Prerequisites

### AWS Account & Permissions

- An active AWS account is required
- IAM permissions for the following services:
    - Amazon EC2 (accelerated instances)
    - Amazon EKS
    - Amazon ECR
    - Amazon S3
    - AWS IAM

!!! warning "Cost Alert"
    Accelerated computing instances (trn1, p5, etc.) incur significant hourly costs.
    Always clean up resources after completing a tutorial.

### Required Tools

| Tool | Min Version | Purpose |
|------|------------|---------|
| AWS CLI | v2.13+ | AWS resource management |
| kubectl | v1.28+ | Kubernetes cluster management |
| eksctl | v0.167+ | EKS cluster creation |
| Docker | v24+ | Container image builds |
| Python | v3.9+ | Scripts and SDK |
| Helm | v3.12+ | Kubernetes package management |

---

## Environment Setup

### 1. Configure AWS CLI

```bash
aws configure
```

```
AWS Access Key ID [None]: YOUR_ACCESS_KEY
AWS Secret Access Key [None]: YOUR_SECRET_KEY
Default region name [None]: us-west-2
Default output format [None]: json
```

!!! tip "Region Selection"
    Trainium instances are not available in all regions.
    We recommend `us-west-2`, `us-east-1`, or `us-east-2`.

### 2. Verify Tool Installation

```bash
# Check versions
aws --version
kubectl version --client
eksctl version
docker --version
python3 --version
helm version
```

### 3. Install Neuron SDK (Optional)

If you need local compilation:

```bash
# Add Neuron repository
pip config set global.extra-index-url https://pip.repos.neuron.amazonaws.com

# Install Neuron compiler and framework
pip install neuronx-cc torch-neuronx
```

---

## Instance Type Guide

### For Training

| Instance | Accelerator | NeuronCores | Memory | Use Case |
|----------|------------|-------------|--------|----------|
| trn1.2xlarge | Trainium ×1 | 2 | 32 GB | Small-scale training/experiments |
| trn1.32xlarge | Trainium ×16 | 32 | 512 GB | Large-scale distributed training |
| trn1n.32xlarge | Trainium ×16 | 32 | 512 GB | EFA networking optimized |

---

## Next Steps

Once your environment is ready, start with the tutorials for your area of interest:

<div class="grid cards" markdown>

-   [:material-rocket-launch: **Inference Infrastructure**](inference/index.md)

    Run vLLM and TGI on Neuron

-   [:material-school: **Training Infrastructure**](training/index.md)

    Build distributed training pipelines

-   [:material-chart-line: **Profiling**](profiling/index.md)

    Performance analysis and optimization

</div>
