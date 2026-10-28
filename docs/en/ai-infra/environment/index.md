---
title: AI Infra Setup
---

# AI Infra Setup

Component-by-component guides for building a large-scale GPU training environment. It covers the full sequence from host setup through the scheduler, containers, storage, and validation.

<div class="grid cards" markdown>

-   :material-server:{ .lg .middle } **DLAMI Host Setup & Validation**

    ---

    Deep Learning AMI-based GPU host setup and driver, EFA, and GDS validation.

    [:octicons-arrow-right-24: DLAMI Host Setup & Validation](dlami-host-setup.md)

-   :material-calendar-check:{ .lg .middle } **Slurm + Pyxis + Enroot**

    ---

    Scheduler and container runtime setup, plus job submission options.

    [:octicons-arrow-right-24: Slurm + Pyxis + Enroot](slurm-pyxis-enroot.md)

-   :material-docker:{ .lg .middle } **Container Image (NGC + EFA)**

    ---

    Building a training container by adding EFA to the NGC image.

    [:octicons-arrow-right-24: Container Image](container-ngc-efa.md)

-   :material-harddisk:{ .lg .middle } **GDS (GPUDirect Storage)**

    ---

    Connect FSx for Lustre directly to GPU memory (GDS over EFA) to accelerate data loading.

    [:octicons-arrow-right-24: GDS](gds-gpudirect-storage.md)

-   :material-check-decagram:{ .lg .middle } **Distributed Training Validation**

    ---

    Measure a go/no-go performance baseline before full training.

    [:octicons-arrow-right-24: Distributed Training Validation](slurm-pyxis-enroot.md#distributed-training-validation)

-   :material-ethernet:{ .lg .middle } **EFA Networking Deep Dive**

    ---

    Inter-node communication principles and NCCL plugin validation.

    [:octicons-arrow-right-24: EFA Networking Deep Dive](../efa-setup.md)

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

</div>
