---
title: AI Infra Orchestration
---

# AI Infra Orchestration

Hands-on labs for running AI workloads on Amazon EKS: the GPU Operator, Ray and KubeRay for distributed training, and NVIDIA Dynamo for inference serving and routing.

<div class="grid cards" markdown>

-   :material-kubernetes:{ .lg .middle } **GPU Operator (Private EKS)**

    ---

    Deploy the NVIDIA GPU Operator to a private EKS cluster.

    [:octicons-arrow-right-24: GPU Operator (Private EKS)](private-eks-gpu-operator/index.md)

-   :material-server-network:{ .lg .middle } **Ray + EFA on EKS**

    ---

    Distributed training and serving on EKS with Ray and EFA.

    [:octicons-arrow-right-24: Ray + EFA on EKS](ray-on-eks-efa/index.md)

-   :material-tune-variant:{ .lg .middle } **Megatron Bridge on KubeRay**

    ---

    LoRA fine-tuning of Qwen3-8B with Megatron Bridge, run as a KubeRay RayJob on a single g6e.12xlarge with EKS Auto Mode.

    [:octicons-arrow-right-24: Megatron Bridge on KubeRay](megatron-kuberay/index.md)

-   :material-call-split:{ .lg .middle } **Disaggregated Inference (Dynamo)**

    ---

    Prefill/decode disaggregated serving on EKS with NVIDIA Dynamo and vLLM.

    [:octicons-arrow-right-24: Disaggregated Inference (Dynamo)](dynamo-disaggregated/index.md)

-   :material-routes:{ .lg .middle } **KV-Aware Routing (Dynamo)**

    ---

    NVIDIA Dynamo's KV-aware router vs round-robin across 2x g6e.xlarge, with the AWS vLLM DLC, Run:ai Model Streamer from a shared EFS volume, and DCGM dashboards.

    [:octicons-arrow-right-24: KV-Aware Routing (Dynamo)](dynamo-kv-routing/index.md)

</div>
