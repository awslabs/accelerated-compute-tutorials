---
title: AI Agents
description: Amazon EKS에서 AI 에이전트를 안전하게 실행하는 핸즈온 레시피
---

# AI Agents

Amazon EKS에서 Agent Sandbox, gVisor, Kata Containers를 활용한 AI 에이전트 실행 가이드입니다.

<div class="grid cards" markdown>

-   :material-shield-lock-outline:{ .lg .middle } **OpenClaw on EKS**

    ---

    Karpenter + Agent Sandbox CRD + gVisor/Kata 격리 + Pod Identity 기반 OpenClaw 에이전트 배포

    [:octicons-arrow-right-24: 가이드 보기](openclaw-eks-lab-guide/index.md)

-   :material-chart-line:{ .lg .middle } **Crypto Trading Agent**

    ---

    Strands Agents SDK + gVisor 샌드박스 기반 프로덕션급 트레이딩 에이전트 구축

    [:octicons-arrow-right-24: 가이드 보기](crypto-trading-agent/index.md)

-   :material-connection:{ .lg .middle } **Agents on EKS with AgentCore Primitives**

    ---

    Bedrock AgentCore 하니스(SDK 컨트랙트)로 감싼 Strands 에이전트를 EKS에서 호스팅하고 AgentCore Memory/Gateway/Identity/Observability 관리형 서비스 소비

    [:octicons-arrow-right-24: 가이드 보기](eks-agentcore-primitives/index.md)

</div>
