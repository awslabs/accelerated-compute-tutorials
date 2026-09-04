---
title: Agent Infrastructure
description: Infrastructure for running AI agents securely on AWS accelerated computing environments
---

# Agent Infrastructure

Hands-on tutorials for running AI agents on Amazon EKS with strong workload isolation. These guides use the [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) project, tiered runtime isolation (gVisor and Kata Containers), keyless Bedrock access via Pod Identity, and Karpenter for node autoscaling.

---

<div class="grid cards" markdown>

-   :material-shield-lock-outline:{ .lg .middle } **OpenClaw on EKS with Agent Sandbox**

    ---

    Deploy OpenClaw AI agents on EKS Standard with Karpenter, the Sandbox CRD for lifecycle management, gVisor and Kata Containers for tiered isolation, Pod Identity for keyless Bedrock access, and network policies for egress control

    [:octicons-arrow-right-24: View Lab Guide](openclaw-eks-lab-guide/index.md)

-   :material-chart-line:{ .lg .middle } **Crypto Trading Agent on EKS**

    ---

    Build a production-grade crypto trading assistant with the Strands Agents SDK, running portfolio analysis and options pricing in air-gapped gVisor sandboxes, with agentgateway routing LLM and MCP tool calls and Cognito for per-user authorization

    [:octicons-arrow-right-24: View Implementation Guide](crypto-trading-agent/index.md)

</div>

---

## Why Agent Sandbox?

The [Agent Sandbox](https://kubernetes.io/blog/2026/03/20/running-agents-on-kubernetes-with-agent-sandbox/) project (SIG Apps) provides a Kubernetes-native abstraction purpose-built for AI agent workloads:

- **Sandbox CRD** — a declarative, single-container environment with stable identity and persistent storage
- **SandboxTemplate** — reusable runtime templates (runc, gVisor, Kata) that decouple workload config from isolation policy
- **SandboxWarmPool** — pre-provisioned sandbox pods that eliminate cold-start latency for agents

---

## Runtime Isolation Tiers

| Runtime | Isolation | Instance Requirement | Use Case |
|---------|-----------|----------------------|----------|
| **runc** | Standard container | Any | Trusted workloads |
| **gVisor** | User-space kernel (Sentry) | Any | Untrusted code execution |
| **Kata Containers** | Hardware-virtualized micro-VM | `.metal` instances | Strongest isolation |
