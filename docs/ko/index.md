---
title: AI Infra on AWS Guide
---

# AI Infra on AWS Guide

AWS 가속 컴퓨팅 인프라에서 대규모 AI/ML 워크로드를 실행하기 위한 **실전 가이드** 모음입니다. 우리 팀의 핵심 솔루션 모션에 맞춰 구성했습니다.

!!! info "언어 안내"
    일부 페이지는 영문으로만 제공됩니다. 한국어 번역이 필요하시면 [이슈를 생성](https://github.com/awslabs/accelerated-compute-tutorials/issues)해 주세요.

## 여기서 시작하세요

<div class="grid cards" markdown>

-   :material-server-network:{ .lg .middle } **AI Infra**

    ---

    칩 종류와 무관하게 필요한 기반 인프라: 가속기 선택, EFA 네트워킹, FSx/S3 스토리지, 용량 확보, NVIDIA GPU 인스턴스.

    [:octicons-arrow-right-24: 시작하기](ai-infra/index.md)

-   :material-chip:{ .lg .middle } **Trainium**

    ---

    AWS 자체 설계 AI 칩 — vLLM Neuron 추론, NKI 커널, 프로파일링, 핸즈온 학습.

    [:octicons-arrow-right-24: 시작하기](aws-ai-chip/index.md)

-   :material-scale-balance:{ .lg .middle } **Frugal AI & Domain Intelligence**

    ---

    제한된 공급 환경에서 모델 압축·컴퓨트 최적화·소형 파인튜닝 오픈웨이트 모델로 비용 효율을 극대화합니다.

    [:octicons-arrow-right-24: 시작하기](frugal-ai/index.md)

-   :material-earth:{ .lg .middle } **Hybrid & Sovereign AI**

    ---

    온프렘·엣지·타 클라우드 컴퓨트를 AWS와 통합하고, 규제·주권 요구에 맞춘 인-컨트리 셀프 호스팅을 지원합니다.

    [:octicons-arrow-right-24: 시작하기](hybrid-sovereign-ai/index.md)

-   :material-robot:{ .lg .middle } **Self-Managed Agents**

    ---

    EKS/Graviton 기반 에이전트 및 셀프 매니지드 워크로드 — OpenClaw, Dynamo, Ray+EFA 등.

    [:octicons-arrow-right-24: 시작하기](self-managed-agents/index.md)

-   :material-school:{ .lg .middle } **교육 및 행사**

    ---

    Neuron Foundations, Neuron Deep Dive 등 AWS 주도 교육 프로그램과 행사 일정을 확인하세요.

    [:octicons-arrow-right-24: 확인하기](events/index.md)

</div>

## 대상 독자

- AI/ML 워크로드를 AWS에서 운영하는 **엔지니어**
- GPU/Trainium 인프라를 설계하는 **아키텍트**
- 비용 최적화와 성능 튜닝이 필요한 **DevOps/MLOps**
