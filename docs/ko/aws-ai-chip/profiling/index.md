---
title: Profiling & Optimization
description: Performance analysis and kernel-level optimization for Neuron workloads
---

# Profiling & Optimization

Learn how to analyze the performance of workloads running on Neuron devices and optimize compute with custom kernels.

---

<div class="grid cards" markdown>

-   :material-magnify:{ .lg .middle } **Neuron Explorer**

    ---

    Visually analyze performance bottlenecks using Neuron Profiler and Explorer tools

    [:octicons-arrow-right-24: View Tutorial](neuron-explorer.md)

-   :material-code-braces:{ .lg .middle } **NKI Kernels**

    ---

    Write custom high-performance kernels using the Neuron Kernel Interface (NKI)

    [:octicons-arrow-right-24: View Tutorial](nki-kernels.md)

</div>

---

## Optimization Workflow

```mermaid
graph LR
    A[Run Workload] --> B[Collect Profile]
    B --> C[Analyze in Explorer]
    C --> D{Bottleneck Found?}
    D -->|Compute Bound| E[Write NKI Kernel]
    D -->|Memory Bound| F[Optimize Tensor Layout]
    D -->|Communication Bound| G[Adjust Distribution Strategy]
    E --> A
    F --> A
    G --> A
```
