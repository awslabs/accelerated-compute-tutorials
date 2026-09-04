---

title: AI 인프라 의사결정 가이드 description: 워크로드 특성에 따라 Bedrock, SageMaker, EKS, EC2, ParallelCluster 중 어디서 AI를 운영할지 결정하는 기술 검토 프레임워크 tags:

- AI 인프라
- FlexAI
- 의사결정
- Bedrock
- SageMaker
- EKS

---

# AI 인프라 의사결정 가이드

**"어디서 AI를 운영할 것인가"** — 이 가이드는 워크로드 분석 → 제약 조건 확인 → 인프라 매칭까지의 기술 검토 프레임워크를 제공합니다.

## Flexible AI (FlexAI)란?

Flexible AI(FlexAI)는 **AWS 위에서 셀프 매니지드 AI 플랫폼을 구성하는 방법론이자 참조 아키텍처** 입니다. 특정 오케스트레이터(EKS, ParallelCluster, SLURM)에 종속되지 않으며, 워크로드 특성에 따라 Managed(Bedrock, SageMaker)와 Self-Managed를 유연하게 조합하는 것을 지향합니다.

**핵심 원칙** : 어떤 단일 서비스에도 락인되지 않고, 워크로드마다 최적의 운영 환경을 선택할 수 있는 유연성(Flexibility)을 확보하는 것. Bedrock API 호출이 최적인 워크로드는 Bedrock으로, GPU 제어가 필요한 워크로드는 EKS/EC2로, 대규모 분산 학습은 ParallelCluster로 — **각각을 적재적소에 배치하는 의사결정 기준** 이 이 가이드의 목적입니다.

## 전제 조건

이 가이드는 **모델이 이미 결정된 상태** 에서 시작합니다. "어떤 모델을 쓸까?"는 별도 검토 영역이며, 여기서는 **그 모델을 어디서, 어떻게 운영할 것인가** 에 집중합니다.

!!! info "단일 정답은 없다" 대부분의 프로덕션 환경은 **하이브리드** 입니다. Bedrock으로 시작하되 일부 워크로드만 Self-Managed로 가는 것이 가장 흔한 패턴입니다. 이 가이드는 **각 워크로드별로** 의사결정을 돕습니다.

## 1. 빠른 판단 — 3분 의사결정 플로우

```
Q1. API 호출만으로 충분한가?
    (모델 커스터마이징 불필요, 프롬프트 엔지니어링만으로 해결)
    ├── Yes → Bedrock (서버리스)
    └── No ↓

Q2. 파인튜닝이 필요한가?
    ├── Bedrock 지원 모델 + 간단한 SFT → Bedrock Custom Model
    ├── SageMaker 지원 모델 + 관리형 원함 → SageMaker
    └── 오픈소스 모델 / 커스텀 학습 파이프라인 → Self-Managed (EKS or EC2) ↓

Q3. 토큰이코노믹스 최적화가 필요한가?
    (모델별 비용 제어, GPU 활용률 최적화, 배칭/캐싱 전략)
    ├── Yes → Self-Managed 확정 (Bedrock/SageMaker에서 불가)
    └── No → Q4로 ↓

Q4. API Throttle이 문제인가?
    (Bedrock 동시 요청 제한, SageMaker 엔드포인트 한계)
    ├── Yes → Self-Managed 확정
    └── No → Managed (Bedrock or SageMaker)

```

## 2. 상세 검토 — 워크로드 특성별 매핑

### 2-1. 추론 (Inference) 워크로드

| 특성 | Bedrock | SageMaker Endpoint | EKS + vLLM | EC2 단독 |
| --- | --- | --- | --- | --- |
| API 호출만 (커스텀 없음) | ⭐ | ✅ | ⚠️ 불필요한 복잡도 | ❌ |
| 프롬프트 엔지니어링 | ⭐ | ✅ | ✅ | ✅ |
| 모델 선택 폭 (오픈소스 포함) | 제한적 | 넓음 | ⭐ 무제한 | ⭐ 무제한 |
| 토큰이코노믹스 (per-model 비용) | ❌ | 제한적 | ⭐ | ⭐ |
| Continuous Batching | ❌ 제어불가 | 제한적 | ⭐ | ⭐ |
| KV Cache 제어 | ❌ | ❌ | ⭐ | ⭐ |
| GPU 활용률 최적화 | ❌ | 제한적 | ⭐ | ⭐ |
| 오토스케일링 | ✅ 자동 | ✅ | ✅ (KEDA) | ❌ 수동 |
| 운영 부담 | ⭐ 없음 | 낮음 | 중간 | 높음 |
| 비용 예측 | 토큰 종량제 | 인스턴스 시간 | 인스턴스 시간 | 인스턴스 시간 |

### 2-2. 학습 (Training) 워크로드

!!!tip "학습은 대부분 EC2 또는 ParallelCluster로 시작" 학습 워크로드에 EKS를 도입하는 것은 **"오케스트레이션이 필요한 시점"** 부터입니다. 단일 모델 실험이나 PoC에서는 EC2 단독이 가장 빠르고, 대규모 분산 학습에는 SLURM 기반 ParallelCluster가 성숙한 선택입니다. EKS는 **멀티 팀 GPU 공유, 학습-서빙 통합 파이프라인** 이 필요할 때 가치가 있습니다.

| 특성 | EC2 단독 | ParallelCluster (SLURM) | EKS + Kubeflow | SageMaker Training |
| --- | --- | --- | --- | --- |
| **PoC / 실험** | ⭐ 최적 (`python train.py`) | ⚠️ 불필요한 복잡도 | ❌ 불필요한 복잡도 | ✅ |
| **대규모 분산 학습** (Multi-Node) | ❌ 수동 관리 | ⭐ SLURM 네이티브 | ✅ (torchrun + Job) | ✅ |
| **SLURM Job 스케줄링** | ❌ | ⭐ 네이티브 | ❌ (K8s 스케줄러) | ❌ |
| **멀티 팀 GPU 공유** | ❌ | ✅ (SLURM partition) | ⭐ (Kueue 쿼터) | ✅ |
| **학습→서빙 통합 파이프라인** | ❌ | ❌ | ⭐ (KFP→KServe) | ✅ (SageMaker Pipelines) |
| **Spot 인스턴스 활용** | ✅ (수동) | ✅ | ✅ (Karpenter) | ✅ |
| **HPC 연계 (MPI, NCCL 최적화)** | ✅ (수동) | ⭐ (EFA 네이티브) | ✅ | ✅ |
| **오픈소스 / 이식성** | ⭐ | ⭐ | ⭐ | ❌ (AWS 종속) |
| **운영 부담** | 높음 | 중간 | 중간~높음 | 낮음 |
| **K8s 전문성 필요** | ❌ | ❌ | ✅ 필수 | ❌ |

**왜 학습에 EKS가 적절하지 않을 수 있는가** :

| # | 근거 | 설명 |
| --- | --- | --- |
| 1 | **K8s 추상화 비용 > 이득** | 단일 GPU Job은 `python train.py`로 끝남. K8s Deployment/Job YAML 작성 + PVC + GPU 스케줄링 설정 시간 > 실제 학습 시간 |
| 2 | **SLURM이 학습에 더 성숙** | 분산 학습(torchrun, DeepSpeed)은 SLURM에서 수십 년간 최적화됨. sbatch 한 줄로 멀티노드 실행. K8s에서는 Job/MPIOperator 설정이 복잡 |
| 3 | **GPU 노드 시작 시간** | EKS에서 GPU Pod 시작 = Karpenter 노드 프로비저닝(2~5분) + 컨테이너 이미지 풀(수 분) + GPU 드라이버 초기화. ParallelCluster는 노드가 상시 할당되어 지연 없이 시작 |
| 4 | **체크포인트/재시작** | SLURM은 Job array, dependency, requeue가 네이티브. K8s에서는 별도 구현 필요 |
| 5 | **잦은 실험 반복** | 하이퍼파라미터 변경 → `python train.py` 바로 재실행 vs KFP Job 제출 대비 이터레이션 속도 10배 차이 |

**EKS가 학습에서 빛나는 경우**:

| 시나리오 | 이유 |
| --- | --- |
| **추론 + 학습 통합 플랫폼** | 서빙 EKS 클러스터에 학습도 올려서 단일 인프라로 관리하고 싶을 때 |
| **멀티 팀 GPU 공유** (10+ 팀) | Kueue 쿼터 + 네임스페이스 분리가 SLURM partition보다 유연 |
| **CI/CD 연계 자동 재학습** | KFP → MLflow → KServe 자동 파이프라인이 가치 있을 때 |

### 2-3. 에이전트 / RAG 워크로드

| 특성 | Bedrock Agents | EKS + LangGraph/Strands | EC2 단독 |
| --- | --- | --- | --- |
| 관리형 에이전트 | ⭐ | ❌ | ❌ |
| 커스텀 오케스트레이션 | 제한적 | ⭐ | ⭐ |
| Tool/MCP 연동 | Bedrock Actions | ⭐ 무제한 | ⭐ 무제한 |
| Knowledge Base (RAG) | Bedrock KB | 직접 구성 | 직접 구성 |
| 멀티모델 라우팅 | ❌ | ⭐ (LiteLLM/AI Gateway) | 가능 |
| 비용 제어 | 토큰 종량 | ⭐ 세밀 | ⭐ 세밀 |

## 3. 핵심 의사결정 포인트 — 가중치 점수제

!!! tip "점수가 높을수록 Self-Managed 방향" 7점 이상이면 Self-Managed를 강력 권장. 4~6점은 하이브리드 고려. 3점 이하면 Managed로 충분.

| # | 조건 | 가중치 | 해당 여부 |
| --- | --- | --- | --- |
| 1 | 토큰이코노믹스 최적화 필요 (per-model 비용, 배칭, 캐싱) | **+3** | ☐ |
| 2 | API Throttle 회피 필요 (동시 요청 수백~수천) | **+3** | ☐ |
| 3 | 오픈소스 모델 필수 (Bedrock 미지원 모델) | +2 | ☐ |
| 4 | GPU 종류/수량 직접 제어 필요 | +2 | ☐ |
| 5 | 온프레미스/하이브리드 요구 (EKS Hybrid Nodes) | +2 | ☐ |
| 6 | 멀티모델 라우팅/A-B 테스트 필요 | +2 | ☐ |
| 7 | 커스텀 서빙 파이프라인 (vLLM 파라미터 튜닝 등) | +1 | ☐ |
| 8 | 기존 Kubernetes 인프라 보유 | +1 | ☐ |
| 9 | 데이터 주권/보안 규제 (클라우드 API 호출 제한) | +1 | ☐ |

!!! warning "+3 조건이 하나라도 해당되면" 토큰이코노믹스 또는 API Throttle 조건에 해당하면 **Bedrock/SageMaker 서버리스로는 구조적으로 불가능** 합니다. Self-Managed가 필수입니다.

| 점수 구간 | 권장 |
| --- | --- |
| **0~3점** | **Bedrock** (또는 SageMaker) — Managed로 충분 |
| **4~6점** | **하이브리드** — Bedrock 기본 + 특정 워크로드만 Self-Managed |
| **7점 이상** | **Self-Managed** (EKS 기반 FlexAI) 권장 |

## 4. Self-Managed 선택 시 — 추론은 EKS, 학습은 상황별

Self-Managed로 결정했다면, **워크로드 유형에 따라 오케스트레이터가 다릅니다**:

```
[추론]
Q5. 멀티모델 서빙 + 오토스케일링?
    ├── Yes → EKS + vLLM + Karpenter/KEDA
    └── No (단일 모델 PoC) → EC2 단독

[학습]
Q6. 어떤 규모의 학습인가?
    ├── PoC / 단일 GPU 실험 → EC2 단독 (초기 구축 비용 최소)
    ├── 대규모 분산 학습 (Multi-Node) → ParallelCluster (SLURM)
    └── 추론 클러스터와 통합 운영 → EKS + KFP (단, K8s 전문성 필요)

[하이브리드]
Q7. 온프레미스 연계?
    ├── Yes → EKS Hybrid Nodes
    └── No → 표준 구성

```

### 워크로드별 권장 오케스트레이터

| 워크로드 | 1순위 | 2순위 | 비고 |
| --- | --- | --- | --- |
| **추론 서빙** (프로덕션) | EKS | EC2 (단일 모델) | EKS의 핵심 강점 영역 |
| **PoC / 실험** | EC2 | — | `python train.py`로 즉시 시작 가능 |
| **대규모 분산 학습** | ParallelCluster | EKS | SLURM이 분산 학습에 더 성숙 |
| **정기 재학습 파이프라인** | EKS (KFP) | SageMaker | 추론과 통합 시 |
| **HPC 워크로드** (사전학습) | ParallelCluster | — | EFA + SLURM 네이티브 |
| **멀티 팀 리소스 공유** | EKS (Kueue) | ParallelCluster (partition) | 10+ 팀이면 EKS 유리 |

### EC2 vs ParallelCluster vs EKS 비교

| 기준 | EC2 단독 | ParallelCluster (SLURM) | EKS |
| --- | --- | --- | --- |
| **핵심 강점** | 단순 구성, 즉시 시작 가능 | 대규모 분산 학습, HPC | 추론 서빙, 마이크로서비스 오케스트레이션 |
| **학습 적합도** | ⭐ PoC | ⭐ 분산 학습 | ⚠️ 통합 필요 시만 |
| **추론 적합도** | ⚠️ 단일 모델만 | ❌ 서빙 미지원 | ⭐ 핵심 |
| **스케일링** | ❌ 수동 | ✅ SLURM auto | ✅ Karpenter/KEDA |
| **K8s 필요** | ❌ | ❌ | ✅ 필수 |
| **운영 부담** | 높음 | 중간 | 중간 |
| **전형적 시작 경로** | PoC → 검증 후 전환 | 학습 전용 | 추론 전용 → 학습 추가 |

---

## 5. 가속기 선택

Self-Managed(EKS/EC2) 선택 후, 다음은 **어떤 GPU/가속기를 쓸 것인가** :

→ **[가속기 선택 가이드](../gpu-selection-guide/)** 참조

요약:

| 워크로드 | 권장 인스턴스 | 이유 |
| --- | --- | --- |
| 대규모 학습 (>70B) | P5/P5en (H100/H200) | NVLink, 대역폭 |
| 추론 (7B~70B) | G6e (L40S) / G7e (RTX PRO 6000) | 비용 효율 + 충분한 VRAM |
| 추론 (< 7B) | G6 (L4) / Inf2 | 저비용 |
| 비용 최적화 학습 | Trn2 (Trainium) | P5 대비 30~50% 저렴 |

## 6. 하이브리드 아키텍처 — 가장 흔한 패턴

!!! success "대부분의 프로덕션은 하이브리드" "전부 Bedrock" 또는 "전부 EKS"는 드뭅니다. 워크로드별로 최적 인프라가 다르기 때문입니다.

### 패턴 A: Bedrock 기본 + 특정 모델만 Self-Managed

```
[에이전트/RAG] → Bedrock (Claude, Titan 등)
[핵심 추론] → EKS + vLLM (오픈소스 모델, 토큰이코노믹스 최적화)
[학습] → EC2 Spot (비용 최적화)

```

**적합** : 대부분 API 호출이지만, 특정 모델의 비용/성능 최적화가 필요한 경우

### 패턴 B: EKS 통합 + Bedrock 보조

```
[전체 서빙] → EKS + vLLM/LiteLLM (AI Gateway)
  ├── 오픈소스 모델 → EKS GPU 노드
  └── Bedrock 모델 → LiteLLM → Bedrock API (fallback/비교용)
[학습 파이프라인] → EKS + Kubeflow
[관측성] → Prometheus + Grafana + Langfuse

```

**적합** : Self-Managed 중심이지만 Bedrock 모델도 활용하고 싶은 경우

### 패턴 C: 온프레미스 + 클라우드 하이브리드

```
[컨트롤 플레인] → EKS (클라우드)
[추론 워커] → EKS Hybrid Nodes (온프레미스 GPU)
[학습] → 클라우드 GPU (Spot/CB)
[데이터] → 온프레미스 (규제 요건)

```

**적합** : 데이터 주권 규제, 기존 온프레미스 GPU 자산 활용

## 7. 의사결정 요약표

| 워크로드 | 가장 쉬운 시작점 | 스케일 업 경로 |
| --- | --- | --- |
| LLM 추론 (API만) | **Bedrock** | → 비용 증가 시 EKS + vLLM |
| LLM 추론 (커스텀 필요) | **EKS + vLLM** | → 모델 추가 시 LiteLLM Gateway |
| 파인튜닝 (간단) | **Bedrock Custom Model** | → 복잡 시 EC2 → EKS + KFP |
| 파인튜닝 (본격) | **EC2 단독** (PoC) | → 정기화 시 EKS + Kubeflow |
| 에이전트/RAG | **Bedrock Agents** | → 커스텀 시 EKS + LangGraph |
| 이미지/비전 추론 | **EKS + vLLM** | → 경량 모델은 CPU Pod 분리 |
| 임베딩 | **Bedrock (Titan)** | → 대량 시 EKS + 자체 모델 |

## 8. 체크리스트

첫 미팅에서 확인할 질문:

| # | 질문 | 답변에 따른 방향 |
| --- | --- | --- |
| 1 | 현재 AI 워크로드가 무엇인가? (추론/학습/에이전트) | 워크로드 유형 파악 |
| 2 | 사용 중이거나 검토 중인 모델은? | Bedrock 지원 여부 확인 |
| 3 | 예상 트래픽은? (QPS, 동시 요청) | Throttle 이슈 판단 |
| 4 | 비용 최적화가 중요한가? 어느 수준까지? | 토큰이코노믹스 필요 여부 |
| 5 | Kubernetes 운영 경험이 있는가? | EKS 도입 가능성 |
| 6 | 데이터 보안/규제 요건은? | 온프레미스/하이브리드 필요 여부 |
| 7 | 기존 GPU 인프라가 있는가? | Hybrid Nodes 고려 |
| 8 | 관리 부담 허용 수준은? (인력, 운영) | Managed vs Self-Managed 방향 |

---

## 참고

- [가속기 선택 가이드](../gpu-selection-guide/) — Self-Managed 결정 후 GPU/인스턴스 매칭
- [EKS Best Practices: AI/ML](https://docs.aws.amazon.com/eks/latest/best-practices/aiml.html) — EKS 위 AI 워크로드 베스트 프랙티스

