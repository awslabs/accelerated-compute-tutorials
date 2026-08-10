# 사전 준비 체크리스트

> **교육**: AWS Neuron Deep Dive (Day 1 & Day 2)  
> **인스턴스**: trn2.3xlarge (1 device, 4 logical cores, 96GB HBM)

---

## 1. 시스템 & 권한 준비

### 공통 (Day 1 & Day 2)

| 구분 | 항목 | 상세 |
| --- | --- | --- |
| **EC2 Quota** | trn2.3xlarge 실행 가능 | Service Quota: `Running On-Demand Trn Instances` ≥ 12 vCPU |
| **EBS** | 최소 200GB gp3 | 모델 캐시 + NEFF 컴파일 캐시 |
| **Security Group** | SSH (22) | 참가자 접속용 |
|  | 포트 8000 | vLLM API 테스트용 |
|  | 포트 3001 | Neuron Explorer Web UI |
|  | 포트 3002 | Neuron Explorer API Backend |
|  | 포트 8888 | Jupyter Notebook (선택) |
| **아웃바운드** | 443 (HTTPS) | HuggingFace Hub, PyPI, ECR 접근 |
| **HuggingFace** | HF 계정 + Access Token | gated 모델(Llama 3.1 등) 사전 라이센스 동의 필요 |
| **IAM — ECR** | ① Public ECR 사용 | `public.ecr.aws/neuron/...` — 별도 IAM 불필요 |
|  | ② Private ECR (고객 계정 복사) | `ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage`, `ecr:GetAuthorizationToken` |

### Day 1 전용

| 구분 | 항목 | 상세 |
| --- | --- | --- |
| **OS/AMI** | Neuron DLAMI (Ubuntu 24.04) | ImageID:ami-098a48f87d9c99e69<br>Neuron 드라이버 + SDK + vLLM 사전 설치|
| **모델 접근** | `meta-llama/Llama-3.2-1B-Instruct` | [HuggingFace에서 Meta 라이센스 동의](https://huggingface.co/meta-llama/Llama-3.2-1B-Instruct) 사전 필요 |

### Day 2 전용

| 구분 | 항목 | 상세 |
| --- | --- | --- |
| **OS/AMI** | Ubuntu 24.04 + Docker | DLC 컨테이너 기반 실습 |
| **Docker** | 설치 + 참가자 docker 그룹 권한 | `usermod -aG docker <user>` |
| **DLC 이미지** | PyTorch Native DLC (Private Beta) | 이미지 URI 별도 공유. 사전 pull 권장 (용량 큼) |
| **추가 디스크** | EBS 총 300GB+ 권장 | NKI 아티팩트, NEFF 캐시, 프로파일 데이터 누적 |


## 2. 사전 지식 (참가자용)

### Day 1 수강 전 확인

| 항목 | 필수/권장 | 설명 |
| --- | --- | --- |
| Docker 기본 사용 | 필수 | `pull`, `run`, `exec`, volume mount |
| Linux CLI | 필수 | SSH 접속, 기본 명령어 (ls, cd, cat, grep) |
| ML/DL 기본 개념 | 필수 | 모델, 추론(inference), 파라미터, 토큰 |
| AWS EC2 기본 | 필수 | 인스턴스 타입, SSH 접속, Security Group |
| LLM 개념 | 권장 | Transformer, attention, 토크나이저 |
| GPU 기반 추론 경험 | 권장 | vLLM 또는 TGI 사용 경험 있으면 유리 |
| HuggingFace 사용 | 권장 | 모델 허브, config.json, tokenizer |

### Day 2 수강 전 확인

| 항목 | 필수/권장 | 설명 |
| --- | --- | --- |
| Day 1 이수 | 필수 | 또는 Neuron 기본 이해 + vLLM 서빙 경험 |
| PyTorch 사용 경험 | 필수 | `model.to()`, forward/backward, DataLoader |
| torch.compile 개념 | 권장 | graph tracing, FX Graph 기본 이해 |
| GPU 커널 개념 | 권장 | CUDA/Triton 경험 있으면 NKI 이해 빠름 |
| Profiler 사용 경험 | 권장 | torch.profiler 또는 Nsight 경험 |

!!! info "학습경로 안내"
    Day1 수강 전 공식 Documents 기반 사전학습을 위한 학습 경로는 [학습경로](../../../aws-ai-chip/education/learning-path.md) 페이지를 참조해 주세요


## 3. 요약 비교

|  | Day 1 | Day 2 |
| --- | --- | --- |
| **주제** | Neuron 기초 & 추론 운영 | PyTorch Native & NKI 최적화 |
| **OS** | Neuron DLAMI | Ubuntu + Docker |
| **환경** | DLAMI 베어메탈 (vLLM 내장) | PyTorch Native DLC (Private Beta) |
| **Docker** | 불필요 | 필요 |
| **실습** | vLLM 배포 → 모니터링 → 튜닝 | NKI 커널 작성 → 벤치마크 → 프로파일링 |
