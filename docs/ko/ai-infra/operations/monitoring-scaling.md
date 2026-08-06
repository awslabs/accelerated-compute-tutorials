# vLLM 프로덕션 모니터링 & 스케일링

| 환경 | EKS + vLLM + Grafana/Prometheus + DCGM Exporter |
| --- | --- |
| 기반 문서 | [AWS EKS 공식: Identify scaling metric thresholds](https://docs.aws.amazon.com/eks/latest/userguide/ml-inference-autoscaling-thresholds.html) |

---

## 1. 전통 ML vs LLM 모니터링 — 왜 다른가?

기존 ML(분류/회귀/탐지 모델) 운영 경험이 있다면, 아래 비교표를 기준으로 LLM 모니터링의 차이점을 이해하면 됩니다.

| 구분 | 전통 ML (분류/회귀/탐지) | LLM 추론 (vLLM) |
| --- | --- | --- |
| **핵심 지표** | Latency, Throughput, Error Rate, Accuracy | + **TTFT, TPOT, KV Cache 사용율, Queue Depth** |
| **병목 자원** | CPU / Memory | **GPU VRAM + Memory Bandwidth** (CPU 거의 무의미) |
| **스케일 시그널** | CPU > 70% 또는 Latency 증가 | **Queue Depth 급증** (CPU/Memory는 참고 불가) |
| **응답 구조** | 요청 → 즉시 응답 (수ms) | 요청 → **스트리밍 토큰 생성** (수초~수십초) |
| **비용 단위** | 요청당 (request) | **토큰당** (input + output tokens) |
| **메모리 특성** | 고정 (모델 로드 후 일정) | **가변** (KV Cache가 요청마다 동적 할당/해제) |
| **배치 처리** | 정적 배치 (batch size 고정) | **Continuous Batching** (동적 합류/이탈) |
| **Cold Start** | 모델 로드 수초 | 모델 로드 **2~10분** + CUDA 워밍업 필요 |
| **OOM 패턴** | 드묾 (메모리 예측 가능) | **빈번** (긴 프롬프트/동시 요청 시 KV Cache 폭증) |
| **GPU 사용율 해석** | 높을수록 좋음 | 30~50%도 정상 (Memory-bound 워크로드) |

### 왜 다른가?

```
[전통 ML]
  입력 → [모델(고정)] → 출력
  - 연산량 일정, 메모리 일정, 응답시간 예측 가능

[LLM 추론]
  입력(가변 길이) → [Prefill: 전체 입력 처리] → 첫 토큰 (TTFT)
                   → [Decode: 토큰 하나씩 생성] → ... → 완료
  - 연산량 = 입력 길이 × 출력 길이에 비례
  - KV Cache = 매 요청마다 동적 할당 (긴 입력 = 메모리 급증)
  - 동시 요청 = KV Cache 경합 → OOM 또는 Preemption

```

### 대시보드 운영 관점 요약

| 전통 ML에서 보던 것 | LLM에서는 이것으로 대체 |
| --- | --- |
| CPU 사용율 → 스케일 판단 | ❌ 의미없음 → **Queue Depth**로 판단 |
| Response Time (단일 값) | **TTFT + TPOT** 분리 필요 (UX 영향 상이) |
| Memory 사용율 | **KV Cache 사용율** (일반 Memory는 참고만) |
| Error Rate | 동일하게 유효 + **Preemption Count** 추가 |
| Model Accuracy | 프로덕션에서는 별도 평가 파이프라인 필요 (offline) |

---

## 2. 모니터링 아키텍처

```
Prometheus (kube-prometheus-stack)
  ├── vLLM /metrics (ServiceMonitor)
  ├── DCGM Exporter (GPU 메트릭)
  └── Node Exporter (CPU/Mem)
        ↓ Remote Write (프로덕션 규모 시)
Amazon Managed Prometheus (AMP)
        ↓
Grafana (or Amazon Managed Grafana)
  ├── vLLM 대시보드
  ├── GPU 대시보드 (DCGM)
  └── Kubernetes 대시보드
        ↓
KEDA ScaledObject
  ├── Queue depth trigger
  └── P95 latency trigger (SLO guardrail)
        ↓
Karpenter NodePool (GPU 노드 자동 프로비저닝)

```

---

## 3. 핵심 모니터링 지표 — 3-Tier 체계

### 🔴 Tier 1 — LLM 서비스 품질 (User-facing SLI)

| 지표 (Prometheus metric) | 의미 | Grafana 패널 | 정상 범위 |
| --- | --- | --- | --- |
| `vllm:e2e_request_latency_seconds` | **E2E 요청 레이턴시** (P50/P95/P99) | Time series | < SLO (모델/용도별 상이) |
| `vllm:time_to_first_token_seconds` | **TTFT** — 첫 토큰까지의 시간. UX에 직결 | Time series | < 1~3초 (입력 길이 의존) |
| `vllm:time_per_output_token_seconds` | **TPOT** — 토큰 생성 속도 | Gauge | 30~100ms (모델 크기/TP 의존) |
| `vllm:num_requests_waiting` | **대기 큐 깊이** — 스케일 아웃의 1차 신호 | Stat + Alert | 0~5 |
| `vllm:num_requests_running` | 현재 처리 중인 요청 수 | Stat | 모델/GPU 의존 |
| `vllm:request_success_total` | 성공 요청 수 (rate 계산용) | Time series | 에러율 < 1% |

### 🟡 Tier 2 — vLLM 내부 상태 (성능 튜닝)

| 지표 | 의미 | 주의 기준 |
| --- | --- | --- |
| `vllm:gpu_cache_usage_perc` | **KV Cache 점유율** | > 80% 알람, > 95% 즉시 대응 |
| `vllm:num_preemptions_total` | 선점(preemption) 발생 횟수 | 급증 시 GPU 메모리 부족 신호 |
| `vllm:prompt_tokens_total` / `generation_tokens_total` | 입출력 토큰 처리량 | 용량 계획용 |
| `vllm:iteration_tokens_total` | 배치 처리 반복당 토큰 수 | 배치 효율 분석 |

### 🟢 Tier 3 — GPU / 인프라 (노드 레벨)

| 지표 (DCGM) | 의미 |
| --- | --- |
| `DCGM_FI_DEV_GPU_UTIL` | GPU Compute 사용율 |
| `DCGM_FI_DEV_MEM_COPY_UTIL` | GPU Memory 대역폭 |
| `DCGM_FI_DEV_FB_USED` / `FB_FREE` | GPU VRAM 사용/잔여 |
| `DCGM_FI_DEV_POWER_USAGE` | 전력 사용 (비용 추적) |
| `DCGM_FI_DEV_ECC_SBE_VOL_TOTAL` | GPU ECC 오류 (하드웨어 이상 감지) |
| `container_cpu_usage_seconds_total` | Pod CPU 사용율 |
| `container_memory_working_set_bytes` | Pod 메모리 |

!!! info "GPU Util 해석 주의" vLLM continuous batching은 메모리 바운드 워크로드 — GPU Compute 사용율이 30~50%여도 정상. CPU처럼 "사용율 높아야 좋다"는 해석은 적용되지 않음.

---

## 4. 스케일 아웃 임계값 — AWS 공식 방법론

> 📎 **출처**: [AWS EKS 공식 문서 — Identify scaling metric thresholds for AI inference](https://docs.aws.amazon.com/eks/latest/userguide/ml-inference-autoscaling-thresholds.html)

### 4-1. 임계값 도출 방법 (k6 부하 테스트)

```
1. 워밍업: 100회 sequential 요청 (CUDA graph 캡처, 커널 컴파일 완료)
2. 10 → 20 → 30 → 40 → 50 → 60 → 70 RPS 구간 점진적 부하 투입
   - 각 구간 60초 유지, 구간 간 30초 휴식
3. Grafana에서 동시 관찰:
   - vllm:num_requests_waiting (큐 깊이)
   - vllm:e2e_request_latency_seconds (레이턴시)
4. 큐 깊이가 0 근처에서 갑자기 급증하는 RPS 지점 = saturation point
5. saturation point 직전 값을 스케일 아웃 임계값으로 설정

```

### 4-2. 스케일 아웃 트리거

| 트리거 | 임계값 (예시) | 의미 | 비고 |
| --- | --- | --- | --- |
| **Queue depth (1차)** | `vllm:num_requests_waiting > N` (per pod) | 대기 요청 초과 시 | demand signal — k6로 N값 실측 |
| **P95 latency (2차, SLO guardrail)** | `p95(e2e_latency) > SLO` | SLO 위반 직전에 선제 스케일 | 긴 프롬프트/이미지 입력 시 유효 |

!!! warning "임계값은 반드시 자체 워크로드로 실측" 위 예시 값은 AWS 문서의 소형 모델(Ministral-3B + g6e.4xlarge) 기준입니다. 모델 크기, GPU 유형, 입력 패턴에 따라 saturation point가 크게 달라지므로 **반드시 자체 k6 부하테스트로 확인** 필요.

### 4-3. 스케일 인 조건

| 조건 | 설정 |
| --- | --- |
| Queue == 0 + Latency < SLO/2 | 5분 이상 지속 시 Scale In |
| `stabilizationWindowSeconds` | **300초 이상** (GPU Pod 기동 느림 — 모델 로딩 2~10분) |
| 한번에 제거하는 Pod 수 | 최대 1개/2분 (보수적) |

---

## 5. KEDA ScaledObject 설정 (예시)

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: vllm-inference-app
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: vllm-inference-app
  minReplicaCount: 1
  maxReplicaCount: 5
  advanced:
    horizontalPodAutoscalerConfig:
      behavior:
        scaleUp:
          stabilizationWindowSeconds: 30   # 빠른 스케일 업
          policies:
            - type: Pods
              value: 2
              periodSeconds: 60
        scaleDown:
          stabilizationWindowSeconds: 300  # 보수적 스케일 다운
          policies:
            - type: Pods
              value: 1
              periodSeconds: 120
  triggers:
    # 1차: 큐 깊이 (demand signal)
    - type: prometheus
      metricType: AverageValue
      metadata:
        serverAddress: http://kube-prometheus-stack-prometheus.monitoring.svc:9090
        query: sum(vllm:num_requests_waiting) or vector(0)
        threshold: "25"          # ← k6 실측 후 조정
        activationThreshold: "1"
    # 2차: P95 latency (SLO guardrail)
    - type: prometheus
      metricType: AverageValue
      metadata:
        serverAddress: http://kube-prometheus-stack-prometheus.monitoring.svc:9090
        query: histogram_quantile(0.95, sum(rate(vllm:e2e_request_latency_seconds_bucket[1m])) by (le)) or vector(0)
        threshold: "5"           # ← SLO 기준으로 조정

```

**KEDA를 쓰는 이유**: HPA 대비 Prometheus 쿼리 직접 연동, activation threshold(스파이크 무시) 지원.

**노드 스케일**: Karpenter가 Pending pod 발생 시 자동으로 GPU 노드 프로비저닝 → Pod 스케일 아웃 + GPU 노드 자동 증설의 **2-tier 구조**.

- [AWS 공식: Autoscale AI inference with HPA and KEDA](https://docs.aws.amazon.com/eks/latest/userguide/ml-inference-autoscaling-hpa-keda.html)

---

## 6. 알림 규칙 (Alert Rules)

| 알림 | 조건 | Severity | 의미 |
| --- | --- | --- | --- |
| VLLMHighQueueDepth | `num_requests_waiting > 50` for 2분 | ⚠️ warning | 스케일링 지연 또는 부하 초과 |
| VLLMHighLatency | `p95(e2e_latency) > SLO` for 2분 | 🔴 critical | SLO 위반 |
| VLLMGPUMemoryCritical | `FB_USED/FB_TOTAL > 95%` for 1분 | 🔴 critical | OOM 임박 |
| VLLMKVCacheFull | `gpu_cache_usage_perc > 95%` for 30초 | 🔴 critical | Preemption/OOM 임박 |
| VLLMPreemptionSpike | `rate(preemptions[5m]) > 5` | ⚠️ warning | 메모리 부족으로 요청 중단 |

---

## 7. 프로덕션 더블체크 포인트

배포 후 시스템 오픈 전 점검:

| # | 항목 | 확인 |
| --- | --- | --- |
| 1 | vLLM `/metrics` 엔드포인트 노출 확인 |  |
| 2 | ServiceMonitor → Prometheus 스크래핑 확인 |  |
| 3 | DCGM Exporter DaemonSet 동작 확인 |  |
| 4 | Grafana 대시보드 구성 (Tier 1/2/3 지표) |  |
| 5 | Alert Rule 등록 (5개) |  |
| 6 | KEDA 설치 & ScaledObject 적용 |  |
| 7 | Karpenter `do-not-disrupt` annotation 적용 |  |
| 8 | **k6 부하테스트 — saturation point 확인** |  |
| 9 | 워밍업 스크립트 (100회) 배포 후 자동 실행 |  |
| 10 | `gpu_memory_utilization` / `max_model_len` 최적화 |  |
| 11 | Scale Out → Scale In 사이클 동작 검증 |  |

### 자주 놓치는 항목

!!! tip "KV Cache 설정" `gpu_memory_utilization=0.85` 권장 (기본 0.9 — 너무 높으면 OOM). `vllm:gpu_cache_usage_perc > 80%` 알람 설정 필수.

!!! tip "Karpenter Consolidation 보호" `yaml # vLLM Pod에 annotation 추가 (Deployment template) metadata: annotations: karpenter.sh/do-not-disrupt: "true" `없으면 Karpenter가 node consolidation 하면서 **서빙 중단** 가능.

!!! tip "GPU 워밍업" 첫 요청은 CUDA graph 캡처, 커널 컴파일로 수배 느림. **배포 후 헬스체크 전 워밍업 요청 100회 선처리** 권장. ReadinessProbe를 워밍업 완료 후에 통과하도록 설정.

!!! tip "max_model_len 검토" 기본값(모델 지원 최대) → KV Cache 메모리 과다 점유 가능. 실제 사용하는 최대 컨텍스트 길이로 조정 (예: 65,536) → 동시 처리량 증가.

---

## 8. 참고 리소스

| 리소스 | 설명 |
| --- | --- |
| [AWS EKS: Identify scaling metric thresholds](https://docs.aws.amazon.com/eks/latest/userguide/ml-inference-autoscaling-thresholds.html) | k6 부하테스트 → 임계값 도출 → KEDA 설정 (end-to-end) |
| [AWS EKS: Autoscale AI inference with HPA and KEDA](https://docs.aws.amazon.com/eks/latest/userguide/ml-inference-autoscaling-hpa-keda.html) | KEDA ScaledObject 상세 설정 |
| [EKS Best Practices: AI/ML](https://docs.aws.amazon.com/eks/latest/best-practices/aiml.html) | 전체 아키텍처 베스트 프랙티스 |
| [Workshop: Generative AI on EKS (NVIDIA GPU)](https://catalog.us-east-1.prod.workshops.aws/workshops/029d6c4e-4775-41c9-85ff-9f5360f32a15/en-US) | vLLM 배포 + ServiceMonitor + Grafana 대시보드 실습 |
| [Workshop: Scaling LLM Inference with vLLM](https://catalog.us-east-1.prod.workshops.aws/workshops/177cf2c8-d451-405b-a463-eb77d38b8617/en-US/vllm/observability) | vLLM 대시보드 JSON 직접 제공, Prometheus 쿼리 포함 |
| [awslabs/ai-ml-observability-reference-architecture](https://github.com/awslabs/ai-ml-observability-reference-architecture) | Prometheus + Grafana + OpenSearch 통합 RA |
| [awslabs/ai-on-eks](https://github.com/awslabs/ai-on-eks) | AI on EKS 전체 리소스 |

