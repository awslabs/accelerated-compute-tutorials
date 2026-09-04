# Neuron Deep Dive (NDD)

!!! note "수강 안내" 
    본 교육은 내부 검토 과정을 거쳐 진행 여부가 결정됩니다. 관심 있는 고객분들은 담당 AM(Account Manager) 또는 SA(Solutions Architect)에게 문의 부탁드립니다.

> **형태** : 3-Day 모듈형 (Day별 독립 수강 가능)<br>**시간**: 각 Day 4시간<br>**대상**: ML 엔지니어, 플랫폼 엔지니어, AI 인프라 담당자<br>**레벨**: 기초 → 심화 → 전문가<br>**사전 지식**: 머신러닝 및 가속기(GPU 등)에 대한 기본적인 이해

## 🎯 코스 개요

Trainium 하드웨어를 이해하고, vLLM Neuron Plugin으로 LLM 추론 서버를 배포·모니터링·최적화하며, PyTorch Native와 NKI 커널까지 다루는 실전 중심 과정입니다.

| Day | 레벨 | 테마 | 대상 |
| --- | --- | --- | --- |
| **Day 1** | 기초 | Neuron 기초 & 추론 운영 | Neuron 경험 없는 엔지니어 |
| **Day 2** | 심화 | PyTorch Native & NKI 최적화 | Day 1 이수 또는 동등 수준 |
| **Day 3** | 전문가 (옵셔널) | vLLM 모델 Onboarding & NAD | Day 1+2 이수, 모델 아키텍처 심화 이해 |

## 📅 Day 1 교육 아젠다

**Neuron 기초 & 추론 운영** | 4시간 | 기초

| 세션 | 주제 | 시간 | 내용 |
| --- | --- | --- | --- |
| 1 | Neuron 플랫폼 이해 | 50분 | Trainium2 하드웨어 아키텍처, NeuronCore-v3, HBM, LNC 구성, Neuron SDK 소프트웨어 스택 |
| 2 | vLLM Neuron & 추론 운영 | 50분 | vLLM Neuron Plugin 아키텍처, 성능 튜닝 이론, 신규 기능 (Disaggregated Inference, Speculative Decoding) |
| 3 | 모니터링 & 프로파일링 이론 | 40분 | neuron-top, Neuron Explorer, Perfetto 프로파일 해석, Accuracy Debugging |
| 4 | 실습 | 75분 | vLLM 서버 배포(Llama-3-8B), 모니터링·프로파일링, 성능 튜닝, 신규 기능 데모 |
| - | Q&A | 5분 |  |

## 📅 Day 2 교육 아젠다

**PyTorch Native & NKI 최적화** | 4시간 | 심화

| 세션 | 주제 | 시간 | 내용 |
| --- | --- | --- | --- |
| 1 | PyTorch Native(TorchNeuron) 심화 | 60분 | torch.compile 파이프라인, 데이터 흐름(HBM→SBUF→PSUM), Mixed Precision, 분산 실행 |
| 2 | NKI 기초 이론 | 50분 | Neuron Kernel Interface 개요, 타일 기반 프로그래밍, PyTorch 연동 3가지 방법 |
| 3 | 실습: PyTorch Native & NKI | 110분 | Eager 모드 추론, NKI 커널 작성, PyTorch 연동, 프로파일링 기반 커널 최적화 |
| - | Q&A | 5분 |  |

## 📅 Day 3 교육 아젠다

**vLLM 모델 Onboarding & NAD** | 4시간 | 전문가 (옵셔널)

| 세션 | 주제 | 시간 | 내용 |
| --- | --- | --- | --- |
| 1 | 모델 Onboarding 프로세스 | 50분 | Onboarding 5단계, Plugin 소스 구조, weight loading 매핑, forward 인터페이스 |
| 2 | Accuracy Debugging | 40분 | 3-Level 검증 프레임워크, 디버깅 7단계, CPU 모드 |
| 3 | 실습: 모델 Onboarding | 110분 | 기존 모델 분석, 신규 모델 구현, 컴파일 & Smoke Test, 정확도 검증 |
| 4 | NAD — AI 기반 커널 개발 소개 | 20분 | NAD 개념, AI 어시스트 워크플로우 데모 |
| - | Q&A | 10분 |  |

## ✅ 사전 준비사항

[:octicons-arrow-right-24: 사전 준비 체크리스트](preparation.md)

## 🔗 연관 과정

- [Neuron Foundations Digest (NFD)](../neuron-foundations/index.md) — 이론 소개 (1~2시간)

