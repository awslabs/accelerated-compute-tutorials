---
title: 시작하기
description: 개발 환경 설정 및 첫 번째 튜토리얼 실행 준비
---

# 시작하기

이 가이드에서는 AI Infra on AWS Guide 를 따라하기 위한 기본 환경을 구성합니다.

---

## 사전 요구사항

### AWS 계정 및 권한

- AWS 계정이 필요합니다
- 아래 서비스에 대한 IAM 권한이 필요합니다:
    - Amazon EC2 (가속 인스턴스)
    - Amazon EKS
    - Amazon ECR
    - Amazon S3
    - AWS IAM

!!! warning "비용 주의"
    가속 컴퓨팅 인스턴스(trn1, p5 등)는 높은 시간당 비용이 발생합니다.
    튜토리얼 완료 후 반드시 리소스를 정리하세요.

### 필수 도구

| 도구 | 최소 버전 | 용도 |
|------|----------|------|
| AWS CLI | v2.13+ | AWS 리소스 관리 |
| kubectl | v1.28+ | Kubernetes 클러스터 관리 |
| eksctl | v0.167+ | EKS 클러스터 생성 |
| Docker | v24+ | 컨테이너 이미지 빌드 |
| Python | v3.9+ | 스크립트 및 SDK |
| Helm | v3.12+ | Kubernetes 패키지 관리 |

---

## 환경 설정

### 1. AWS CLI 구성

```bash
aws configure
```

```
AWS Access Key ID [None]: YOUR_ACCESS_KEY
AWS Secret Access Key [None]: YOUR_SECRET_KEY
Default region name [None]: us-west-2
Default output format [None]: json
```

!!! tip "리전 선택"
    Trainium 인스턴스는 모든 리전에서 사용 가능하지 않습니다.
    `us-west-2`, `us-east-1`, `us-east-2` 리전을 권장합니다.

### 2. 도구 설치 확인

```bash
# 버전 확인
aws --version
kubectl version --client
eksctl version
docker --version
python3 --version
helm version
```

### 3. Neuron SDK 설치 (선택)

로컬에서 컴파일이 필요한 경우:

```bash
# Neuron 리포지토리 추가
pip config set global.extra-index-url https://pip.repos.neuron.amazonaws.com

# Neuron 컴파일러 및 프레임워크 설치
pip install neuronx-cc torch-neuronx
```

---

## 인스턴스 타입 가이드

### 학습용

| 인스턴스 | 가속기 | NeuronCores | 메모리 | 용도 |
|---------|--------|-------------|--------|------|
| trn1.2xlarge | Trainium ×1 | 2 | 32 GB | 소규모 학습/실험 |
| trn1.32xlarge | Trainium ×16 | 32 | 512 GB | 대규모 분산 학습 |
| trn1n.32xlarge | Trainium ×16 | 32 | 512 GB | EFA 네트워킹 최적화 |

---

## 다음 단계

환경이 준비되었으면 관심 분야의 튜토리얼을 시작하세요:

<div class="grid cards" markdown>

-   [:material-rocket-launch: **추론 인프라**](aws-ai-chip/inference/index.md)

    vLLM, TGI를 Neuron에서 실행

-   [:material-school: **학습 인프라**](aws-ai-chip/training/index.md)

    분산 학습 파이프라인 구축

-   [:material-chart-line: **프로파일링**](aws-ai-chip/profiling/index.md)

    성능 분석 및 최적화

</div>
