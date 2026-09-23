---
title: Self-Managed Agents
---

# Self-Managed Agents

EKS/Graviton 기반의 에이전트 및 셀프 매니지드 AI 워크로드 — 커스텀 에이전트, 오케스트레이션, 셀프 호스팅 플랫폼.

<div class="grid cards" markdown>

-   :material-shield-lock-outline:{ .lg .middle } **OpenClaw on EKS**

    ---

    Karpenter + Agent Sandbox CRD + gVisor/Kata 격리 기반 OpenClaw 에이전트 배포

    [:octicons-arrow-right-24: 보기](openclaw-eks-lab-guide/index.md)

-   :material-chart-line:{ .lg .middle } **Crypto Trading Agent**

    ---

    Strands SDK + gVisor 샌드박스 기반 프로덕션급 트레이딩 에이전트

    [:octicons-arrow-right-24: 보기](crypto-trading-agent/index.md)

-   :material-call-split:{ .lg .middle } **Disaggregated Inference (Dynamo)**

    ---

    NVIDIA Dynamo + vLLM 기반 Prefill/Decode 분리 서빙 (EKS)

    [:octicons-arrow-right-24: 보기](dynamo-disaggregated/index.md)

-   :material-server-network:{ .lg .middle } **Ray + EFA on EKS**

    ---

    EKS에서 Ray + EFA 기반 분산 학습 및 서빙

    [:octicons-arrow-right-24: 보기](ray-on-eks-efa/index.md)

-   :material-school:{ .lg .middle } **Distributed Training**

    ---

    셀프 매니지드 클러스터에서의 분산 학습 패턴

    [:octicons-arrow-right-24: 보기](distributed-training.md)

-   :material-language-python:{ .lg .middle } **PyTorch Native**

    ---

    EKS에서 PyTorch 네이티브 분산 학습

    [:octicons-arrow-right-24: 보기](pytorch-native.md)

-   :material-kubernetes:{ .lg .middle } **GPU Operator (Private EKS)**

    ---

    프라이빗 EKS 클러스터에 NVIDIA GPU Operator 배포

    [:octicons-arrow-right-24: 보기](private-eks-gpu-operator/index.md)

</div>
