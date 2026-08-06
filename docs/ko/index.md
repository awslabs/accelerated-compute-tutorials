---
title: Accelerated Compute Tutorials
---

# Accelerated Compute Tutorials

AWS 가속 컴퓨팅 인프라에서 대규모 AI/ML 워크로드를 실행하기 위한 **실전 튜토리얼** 모음입니다.

---

## 🚀 여기서 시작하세요

<div class="grid cards" markdown>

-   :material-chip:{ .lg .middle } **AWS AI Chip (Trainium)**

    ---

    AWS의 자체 설계 AI 칩에서 추론·학습·커널 개발을 시작하세요. vLLM 서빙, PyTorch 분산 학습, NKI 커스텀 커널까지 모두 다룹니다.

    [:octicons-arrow-right-24: 시작하기](aws-ai-chip/index.md)

-   :material-expansion-card:{ .lg .middle } **NVIDIA GPU on AWS**

    ---

    P5, G6e, G7e 등 NVIDIA GPU 인스턴스에서 vLLM·SGLang 추론, 워크로드별 인스턴스 선택, 비용 최적화 가이드를 제공합니다.

    [:octicons-arrow-right-24: 시작하기](nvidia-gpu/index.md)

-   :material-server-network:{ .lg .middle } **AI Infra 공통**

    ---

    칩 종류와 무관하게 필요한 인프라 설계: EFA 네트워킹, FSx/S3 스토리지, Capacity Blocks 확보, Docker 컨테이너 구성.

    [:octicons-arrow-right-24: 시작하기](ai-infra/index.md)

-   :material-update:{ .lg .middle } **업데이트**

    ---

    Neuron SDK 릴리즈 노트와 주요 변경사항을 정리합니다.

    [:octicons-arrow-right-24: 확인하기](updates/index.md)

</div>

---

## 🎯 작업별 빠른 링크

<div class="grid cards" markdown>

-   :material-robot:{ .lg .middle } **LLM 추론 서빙**

    ---

    vLLM, TGI 등으로 대규모 언어 모델을 서빙하고 싶다면

    [:octicons-arrow-right-24: Neuron에서 vLLM](aws-ai-chip/inference/vllm/index.md) · [:octicons-arrow-right-24: GPU에서 vLLM](nvidia-gpu/inference/vllm-on-gpu.md)

-   :material-school:{ .lg .middle } **분산 학습**

    ---

    PyTorch Native, NxDT로 대규모 모델을 학습하고 싶다면

    [:octicons-arrow-right-24: 학습 가이드](aws-ai-chip/training/index.md)

-   :material-code-braces:{ .lg .middle } **NKI 커널 개발**

    ---

    NeuronCore를 직접 프로그래밍하여 최적화 커널을 작성하고 싶다면

    [:octicons-arrow-right-24: NKI 시작하기](aws-ai-chip/nki/index.md)

-   :material-chart-line:{ .lg .middle } **성능 프로파일링**

    ---

    Neuron Explorer로 병목을 분석하고 성능을 최적화하고 싶다면

    [:octicons-arrow-right-24: 프로파일링](aws-ai-chip/profiling/index.md)

</div>

---

## 대상 독자

- AI/ML 워크로드를 AWS에서 운영하는 **엔지니어**
- GPU/Trainium 인프라를 설계하는 **아키텍트**
- 비용 최적화와 성능 튜닝이 필요한 **DevOps/MLOps**
