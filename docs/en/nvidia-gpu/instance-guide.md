# NVIDIA GPU Instances

This guide introduces the NVIDIA GPU-based Amazon EC2 instances offered by AWS. It covers the distinction between the P and G families, the mapping of NVIDIA GPU architectures to EC2 instances, instance specifications, use cases, and key benefits — helping you choose the right instance for your workload.

---

## 1. P-family vs G-family Instances

AWS's NVIDIA GPU instances fall into two broad families.

<div class="grid cards" markdown>

-   :material-server-network:{ .lg .middle } __P family: high-performance GPUs for AI training and large-scale inference__

    ---

    - Equipped with large-capacity, high-bandwidth memory (HBM)
    - Typically configured in units of 8 GPUs
    - For distributed training, many GPUs and nodes are linked over a high-speed network and run as a cluster
    - Built-in high-speed GPU-to-GPU and node-to-node communication
    - Scale out to tens of thousands of GPUs with EC2 UltraClusters

-   :material-expansion-card:{ .lg .middle } __G family: cost-efficient GPUs for inference and graphics__

    ---

    - Equipped with GDDR memory
    - Configurable in units of 1–8 GPUs, offering a wide range of sizing options
    - Optimized for performance and cost on a single GPU or node

</div>

---

## 2. Amazon EC2 Instance ↔ NVIDIA GPU Mapping

As the first cloud provider to offer GPU instances, AWS has continuously expanded its portfolio in step with NVIDIA's latest GPU roadmap. The Amazon EC2 instances corresponding to each NVIDIA GPU architecture generation are shown below.

<figure markdown>
  ![Amazon EC2 instances mapped to NVIDIA GPU architecture generations — from Kepler (2012) to Rubin (2026), showing the corresponding P-family (high-end) and G-family (general-purpose) instances by architecture. Sun icons mark instances available in the Seoul region; P2, P3, and G3 are discontinued](mapping.png){ width="960" }
</figure>

---

## 3. Latest Blackwell-Architecture Instances

AWS's Blackwell-based instances come in four variants, depending on workload scale and characteristics.

<div class="grid cards" markdown>

-   :material-server:{ .lg .middle } __[P6-B200/B300](#31-p6-b200b300)__

    ---

    Server-scale frontier model training and inference

-   :material-server-network:{ .lg .middle } __[P6e-GB200/GB300 (UltraServer)](#32-p6e-gb200gb300-ultraserver)__

    ---

    Rack-scale frontier models

-   :material-expansion-card:{ .lg .middle } __[G7e](#33-g7e)__

    ---

    High-performance inference, graphics, and media

-   :material-expansion-card:{ .lg .middle } __[G7](#34-g7)__

    ---

    Cost-efficient, general-purpose inference and graphics

</div>

### 3.1 P6-B200/B300

These instances pair eight NVIDIA Blackwell (B200) or Blackwell Ultra (B300) GPUs in a single node, supporting a broad range of AI workloads from large-scale training to low-latency inference. Compared with the previous-generation Hopper (H100/H200), they deliver major gains across memory, bandwidth, compute, and quantization — processing the same workload faster and with fewer GPUs. The B300 in particular carries 268GB of memory per GPU, accommodating larger batches, less sharding, and longer contexts that were previously hard to support. Together with higher memory bandwidth and hardware-native FP8/FP4, this yields up to 2× training throughput and 40–60% lower decode latency in inference. FP8 preserves roughly 99% accuracy while doubling throughput (0.5–1.5% accuracy loss), and NVFP4 delivers 4× memory savings (2–5% accuracy trade-off) while halving MoE communication volume. The B300 also improves attention throughput by ~30% via 2× higher SFU throughput (softmax, exp) and TMA-based optimized kernels (such as FlashAttention-4), and reduces checkpoint size by ~25% through a dedicated hardware Decompression Engine (DE) and the nvCOMP library, improving model-loading efficiency. Notably, among the major cloud service providers (CSPs), AWS is the only one to offer the B300 in an NVL8 configuration.

> 💡 For a deeper look at the P6-B300, see the [P6-B300 APJ launch page](https://awslabs.github.io/accelerated-compute-tutorials/en/updates/p6-b300-seoul-launch/).

| Specification | Value (P6-B300) |
|-----------------------|------------------------------------------------------|
| GPU | 8× NVIDIA B300 |
| GPU memory | 2,144GB HBM3e (268GB per GPU) |
| GPU memory bandwidth | 7.7 TB/s |
| CPU | 5th Gen Intel Xeon Scalable (Emerald Rapids), 192 vCPU |
| System memory | 4,096 GiB |
| Networking | 6.4 Tbps (EFAv5), 300 Gbps dedicated ENA |
| GPU-to-GPU interconnect | NVLink 5 (1.8 TB/s) |
| Local storage | 30TB local NVMe |

#### Benefits for Training

- 🧠 **Large-capacity memory simplifies infrastructure** — 180GB (B200) / 268GB (B300) per GPU supports larger batches, less sharding, and longer contexts.
  Example: a 70B full fine-tune (Adam + FSDP) shrinks from 16 H100 GPUs (2 nodes) to 8 B200 GPUs (1 node) — halving the footprint and reducing sharding complexity, distributed-training overhead, and debugging effort.
- ⚡ **2× compute with FP8** — hardware-native MXFP8 preserves roughly 99% accuracy while doubling throughput.

#### Benefits for Inference

- 🚀 **Higher memory bandwidth removes the decode bottleneck** — 8 TB/s (B200) vs 4.8 TB/s (H200).
  → 66% more bandwidth translates to 40–60% lower decode latency and faster token generation.
- 💾 **Memory consolidation saves GPUs** — a model that needed two H200 GPUs fits on a single B200 GPU.
  → Lowers GPU cost and makes it possible to serve 128K+ long-context windows.
- 🔗 **Stronger GPU-to-GPU communication** — NVLink 5 provides 1.8 TB/s of bidirectional bandwidth per GPU (roughly 2× Hopper), removing tensor-parallel and MoE all-to-all bottlenecks.
  → Cuts multi-GPU inference latency by 30–50%.
- 🎯 **Quantization + speculative decoding** — FP8 doubles throughput (0.5–1.5% accuracy trade-off) and NVFP4 delivers 4× memory savings (2–5% accuracy trade-off), leaving headroom for larger batches and KV cache.
- 💰 **Better cost per token** — the per-GPU price is higher, but throughput gains lower the cost per token, with increasingly favorable unit economics at scale.

### 3.2 P6e-GB200/GB300 (UltraServer)

These instances bind up to 72 NVIDIA B200/B300 GPUs into a single NVLink domain that operates as one massive compute unit. They are purpose-built for training and serving trillion-parameter frontier models, MoE models, and reasoning models.

| Specification | Value |
|--------------|--------------------------------------------|
| GPU | 72× NVIDIA B200/B300 (rack scale) |
| Architecture | Superchip (Grace CPU + 2 Blackwell GPUs) |
| GPU memory | 13.3TB (GB200) – 20.1TB (GB300) HBM3e |
| CPU | NVIDIA Grace (Arm-based) |
| Networking | Up to 28.8 Tbps (EFAv4) |
| GPU-to-GPU interconnect | NVLink 5 (1.8 TB/s), single NVLink domain |
| Distinction | First liquid-cooled EC2 instance |

#### Key Benefits

- 🔗 **Rack-scale NVLink domain** — binds up to 72 GPUs into one compute unit, minimizing inter-node communication bottlenecks. This is the first AWS instance to adopt NVL72.
- 🧩 **Grace Blackwell superchip** — two Blackwell GPUs and a Grace CPU sit in a single compute module, boosting CPU-to-GPU bandwidth.
- 📈 **Scales beyond a single server** — combines the equivalent of nine 8-GPU servers, enabling the training and deployment of trillion-parameter models.

### 3.3 G7e

A high-performance, general-purpose GPU instance that delivers top-of-portfolio performance for workloads needing both graphics and AI, with competitive price-performance versus P5 — especially when using FP4. Improved across memory, bandwidth, compute, and media processing over the previous-generation G6e (L40S), it delivers 5× agentic AI, 7× genomics sequencing, 3.3× text-to-video generation, and 2× recommendation-system performance.

| Specification | Value |
|-------------------|--------------------------------------------------------|
| GPU | Up to 8× NVIDIA RTX Pro 6000 Blackwell Server Edition |
| GPU memory | 96GB GDDR7 per GPU, 1.6 TB/s bandwidth |
| CPU | 5th Gen Intel Xeon Scalable (Emerald Rapids), 192 vCPU |
| System memory | Up to 2,048 GiB |
| Networking | Up to 800 Gbps (EFAv4) |
| Local storage | Up to 15.2TB SSD |
| Media engines | 4 encoders + 4 decoders |

#### Key Benefits vs G6e

- 💾 **2× GPU memory and FP4** — 96GB (up from 48GB) plus FP4 lets you deploy models up to 160B parameters on a single GPU, with no tensor parallelism required.
- 🚀 **1.85× memory bandwidth** — faster model loading and real-time agentic and multimodal AI inference.
- ⚡ **4× GPU-to-GPU and network bandwidth, plus GPUDirect** — lower latency for multi-GPU inference, small-scale fine-tuning, and domain-specialized training.
- 🔌 **4× CPU-to-GPU bandwidth (PCIe Gen5 x16)** — higher throughput for recommendation systems, data analytics, and RAG workloads.
- 🎨 **Up to 2× rendering performance** — 4× gaming frame rates with neural shaders, RTX Mega Geometry, and DLSS 4; four encoders and four decoders accelerate professional video processing.

### 3.4 G7

A general-purpose, GPU-accelerated instance that handles ML inference, graphics, and data analytics cost-efficiently. Versus the previous-generation G6 (L4), it delivers 2× inference performance, roughly 35% lower cost per token, and up to 30% better price-performance.

| Specification | Value |
|-------------------|--------------------------------------------------------|
| GPU | Up to 8× NVIDIA RTX Pro 4500 Blackwell Server Edition |
| GPU memory | 32GB GDDR7 per GPU, 700 GB/s bandwidth |
| CPU | Intel Granite Rapids, 192 vCPU |
| System memory | Up to 768 GB |
| Networking | Up to 700 Gbps EFA (on .8xlarge and larger) |
| Local storage | Up to 7.6TB SSD |
| Media engines | 3 encoders + 3 decoders |

#### Key Benefits vs G6

- 🚀 **2.45× GPU memory bandwidth (736 GB/s)** — up to 2× inference for models like Llama and BERT, translating to roughly 35% lower cost per token.
- 💾 **1.33× GPU memory (32GB)** — supports larger AI models and more complex 3D scenes, and deploys models up to 32B parameters on a single GPU.
- 🌐 **7× network bandwidth (700 Gbps EFA)** — cuts I/O wait time for data-intensive analytics and multimodal pipelines by up to 40%.
- 🔌 **4× CPU-to-GPU bandwidth (PCIe Gen5 x16)** — accelerates data transfer for RAG inference, recommendation systems, and preprocessing-heavy workloads.
- ⚙️ **~1.5× FP16 TFLOPs and ~2× CPU performance** — higher raw GPU throughput, with Intel Granite Rapids accelerating CPU-bound stages.
- 🎬 **1.6× concurrent video streams** — processes broadcast-grade 4K/8K video with three encoders and three decoders.

## 4. Instance Specifications

Detailed specifications by generation for AWS's NVIDIA GPU instances. The tables scroll horizontally.

### P-family Specifications

| Specification | P4d/P4de | P5 | P5e | P5en | P6-B200 | P6-B300 | P6e-GB200 | P6e-GB300 |
|---|---|---|---|---|---|---|---|---|
| Architecture | Ampere | Hopper | Hopper | Hopper | Blackwell | Blackwell | Blackwell | Blackwell |
| Release | '20.11 | '23.7 | '24.9 | '24.12 | '25.5 | '25.11 | '25.7 | '25.12 |
| NVIDIA GPU | A100 ×8 | H100 ×8 | H200 ×8 | H200 ×8 | B200 ×8 | B300 ×8 | B200 ×72 | B300 ×72 |
| GPU memory | 320GB HBM2 / 640GB HBM2e | 640GB HBM3 | 1,128GB HBM3 | 1,128GB HBM3 | 1,440GB HBM3e | 2,144GB HBM3e | 13.3TB HBM3e | 20.1TB HBM3e |
| GPU memory bandwidth | 1.6 / 2 TB/s | 3.35 TB/s | 4.8 TB/s | 4.8 TB/s | 7.7 TB/s | 7.7 TB/s | 8.0 TB/s | 8.0 TB/s |
| CPU | Intel Cascade Lake | AMD EPYC 7R13 | AMD EPYC 7R13 | Intel Sapphire Rapids | Intel Emerald Rapids | Intel Emerald Rapids | NVIDIA Grace (Arm) | NVIDIA Grace (Arm) |
| Network adapter | EFA/ENA | EFAv2 | EFAv2 | EFAv3 | EFAv4 | EFAv4 | EFAv4 | EFAv4 |
| Network bandwidth | 400 Gbps | 3.2 Tbps | 3.2 Tbps | 3.2 Tbps | 3.2 Tbps | 6.4 Tbps | 28.8 Tbps | Undisclosed |
| GPU-to-GPU interconnect | 600 GB/s | 900 GB/s | 900 GB/s | 900 GB/s | 1,800 GB/s | 1,800 GB/s | 1,800 GB/s | 1,800 GB/s |
| EBS bandwidth | 19 Gbps | 80 Gbps | 80 Gbps | 100 Gbps | 100 Gbps | 100 Gbps | 1,080 Gbps | Undisclosed |
| Nitro version | Nitro v3 | Nitro v4 | Nitro v4 | Nitro v5 | Nitro v6 | Nitro v6 | Nitro v6 | Nitro v6 |
| Seoul region (as of Aug '26) | Supported (P4d) | Not supported | Not supported | Supported | Not supported | Not supported | Not supported | Not supported |

---

### G-family Specifications

| Specification | G4dn | G5g | G5 | G6 | G6f | G6e | G7 | G7e |
|---|---|---|---|---|---|---|---|---|
| Architecture | Turing | Turing | Ampere | Ada Lovelace | Ada Lovelace | Ada Lovelace | Blackwell | Blackwell |
| Release | '19.3 | '22.11 | '21.11 | '24.6 | '25.7 | '24.9 | '26.6 | '26.1 |
| NVIDIA GPU | T4 ×8 | T4G ×2 | A10G ×8 | L4 ×8 | L4 fractional (½, ¼, ⅛) | L40S ×8 | RTX Pro 4500 Blackwell | RTX Pro 6000 Blackwell |
| Memory per GPU | 16GB GDDR6 | 16GB GDDR6 | 24GB GDDR6 | 24GB GDDR6 | 3–12GB GDDR | 48GB GDDR6 w/ ECC | 32GB GDDR7 | 96GB GDDR7 |
| Total GPU memory | 128GB | 32GB | 192GB | 192GB | 12GB | 384GB | 256GB | 768GB |
| CPU | Intel Cascade Lake | AWS Graviton2 (Arm) | 2nd Gen AMD EPYC | 3rd Gen AMD EPYC | 3rd Gen AMD EPYC | 3rd Gen AMD EPYC | Intel Granite Rapids | Intel Emerald Rapids |
| vCPU | 96 | 64 | 192 | 192 | 16 | 192 | 192 | 192 |
| Instance memory | 384GB | 128GB | 768GB | 768GB | 64GB | 1,536GB | 768GB | 2,048GB |
| Networking | 100 Gbps EFA | 25 Gbps | 100 Gbps EFA | 100 Gbps EFA | 25 Gbps EFA | 400 Gbps EFA | 700 Gbps EFA | 1,600 Gbps EFA |
| EBS bandwidth | 19 Gbps | 19 Gbps | 19 Gbps | 60 Gbps | 6 Gbps | 60 Gbps | 80 Gbps | 100 Gbps |
| Seoul region (as of Aug '26) | Supported | Supported | Supported | Supported | Supported | Supported | Not supported | Supported |

Figures reflect the largest size in each instance family.

---

## 5. Instance Recommendations by Use Case

The right instance family and generation depend on your workload. Recommended instances for representative use cases are listed below. For more detailed selection criteria, see the Accelerator Selection Guide.

| Use case | Recommended instances |
|------------------------------------------------------------------------|-------------------------------------------|
| Frontier / ultra-large model training (hundreds of billions to trillions of parameters) | P6e-GB200/GB300 (UltraServer), P6-B200/B300 |
| Large-scale model training and fine-tuning (tens to hundreds of billions of parameters) | P6-B200/B300, P5en |
| Large-scale model inference (70B+, latency-sensitive) | P6-B200/B300, P5en |
| Medium-scale model inference (agentic, multimodal AI) | G7e, G6e |
| Small-to-medium-scale inference (general LLM and vision model serving) | G6e, G6, G5 |
| Real-time rendering, graphics, visualization | G7e, G7, G6e |
| Video processing and transcoding | G7e, G6e |
| Recommendation systems, data analytics, RAG | G7e, G6e |
| Development, prototyping, small-scale experiments | G6, G6f, G5, G4dn |

---

## 6. Instance Availability by Region

Please see the [Amazon EC2 instance types by Region](https://docs.aws.amazon.com/ec2/latest/instancetypes/ec2-instance-regions.html) page.

