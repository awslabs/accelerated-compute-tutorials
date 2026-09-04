---
title: AI Infra on AWS Guide
---

# AI Infra on AWS Guide

AWS 가속 컴퓨팅 인프라에서 대규모 AI/ML 워크로드를 실행하기 위한 **실전 튜토리얼** 모음입니다.

!!! info "언어 안내"
    일부 페이지는 영문으로만 제공됩니다. 한국어 번역이 필요하시면 [이슈를 생성](https://github.com/awslabs/accelerated-compute-tutorials/issues)해 주세요.


---

## 🚀 여기서 시작하세요

<div class="grid cards" markdown>

-   :material-server-network:{ .lg .middle } **AI Infra**

    ---

    칩 종류와 무관하게 필요한 인프라 설계: EFA 네트워킹, FSx/S3 스토리지, Capacity Blocks 확보, Docker 컨테이너 구성.

    [:octicons-arrow-right-24: 시작하기](ai-infra/index.md)

-   :material-chip:{ .lg .middle } **AWS Trainium**

    ---

    AWS의 자체 설계 AI 칩에서 추론·학습·커널 개발을 시작하세요. vLLM 서빙, PyTorch 분산 학습, NKI 커스텀 커널까지 모두 다룹니다.

    [:octicons-arrow-right-24: 시작하기](aws-ai-chip/index.md)

-   :material-expansion-card:{ .lg .middle } **NVIDIA GPU**

    ---

    P5, G6e, G7e 등 NVIDIA GPU 인스턴스에서 vLLM·SGLang 추론, 워크로드별 인스턴스 선택, 비용 최적화 가이드를 제공합니다.

    [:octicons-arrow-right-24: 시작하기](nvidia-gpu/index.md)

-   :material-flask:{ .lg .middle } **AI Infra 레시피**

    ---

    EKS, ParallelCluster, Trainium, NVIDIA GPU 등 다양한 플랫폼에서 AI 워크로드를 구축하는 시나리오별 핸즈온 레시피.

    [:octicons-arrow-right-24: 시작하기](recipes/index.md)

-   :material-school:{ .lg .middle } **교육 및 행사**

    ---

    Neuron Foundations, Neuron Deep Dive 등 AWS 주도 교육 프로그램과 행사 일정을 확인하세요.

    [:octicons-arrow-right-24: 확인하기](events/index.md)

-   :material-newspaper:{ .lg .middle } **최신소식**

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


-   :material-school:{ .lg .middle } **분산 학습**

    ---

    PyTorch Native, NxDT로 대규모 모델을 학습하고 싶다면


-   :material-code-braces:{ .lg .middle } **NKI 커널 개발**

    ---

    NeuronCore를 직접 프로그래밍하여 최적화 커널을 작성하고 싶다면


-   :material-chart-line:{ .lg .middle } **성능 프로파일링**

    ---

    Neuron Explorer로 병목을 분석하고 성능을 최적화하고 싶다면


</div>

---

## 대상 독자

- AI/ML 워크로드를 AWS에서 운영하는 **엔지니어**
- GPU/Trainium 인프라를 설계하는 **아키텍트**
- 비용 최적화와 성능 튜닝이 필요한 **DevOps/MLOps**
