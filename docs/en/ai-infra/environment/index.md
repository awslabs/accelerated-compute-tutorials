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

</div>
