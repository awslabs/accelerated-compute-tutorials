---
title: Trainium
---

# AWS Trainium

Practical guides for running large-scale AI workloads on **AWS Trainium** — the AWS-designed AI chip. Trainium is a powerful accelerator option you can choose alongside GPUs, built for strong price-performance on both training and inference.

You can run Trainium on self-managed infrastructure — Amazon EKS, Amazon ECS, AWS Batch, or Amazon EC2 — or with Amazon SageMaker.

<div class="grid cards" markdown>

-   :material-robot:{ .lg .middle } **Inference**

    ---

    Deployment guides by serving framework (vLLM, TGI). OpenAI-compatible APIs, continuous batching, and speculative decoding.

    [:octicons-arrow-right-24: Inference Guide](inference/index.md)

-   :material-school:{ .lg .middle } **Training**

    ---

    Distributed training of large models with NxDT, PyTorch Native, and Optimum Neuron — from pre-training to LoRA fine-tuning.

-   :material-code-braces:{ .lg .middle } **NKI Kernels**

    ---

    Write and optimize custom kernels that program NeuronCores directly, using Python/NumPy-style tile programming.

    [:octicons-arrow-right-24: NKI Kernels](profiling/nki-kernels.md)

-   :material-chart-line:{ .lg .middle } **Profiling**

    ---

    Performance analysis with Neuron Explorer, covering the framework, NKI, compiler, and runtime layers.

    [:octicons-arrow-right-24: Profiling Guide](profiling/index.md)

-   :material-cog:{ .lg .middle } **Advanced Configuration**

    ---

    Hardware-level optimization options such as Logical NeuronCore configuration and mixed precision.

-   :material-play-circle:{ .lg .middle } **Learning Videos**

    ---

    Video content on NeuronCore concepts and architecture.

</div>
