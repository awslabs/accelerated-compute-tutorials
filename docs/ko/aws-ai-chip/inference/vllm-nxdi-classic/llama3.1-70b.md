!!! warning "Classic 가이드"
    이 문서는 NxD Inference (Maintenance Mode) 기반 가이드입니다.
    신규 배포는 [vLLM Neuron Plugin](../vllm/index.md)을 권장합니다.

# Serving Llama3.1 70B Instruct on Trainium2 with vLLM + NxDI

이 가이드는 **AWS Trainium2 `trn2.48xlarge`** 인스턴스에서 **vLLM 0.13 + NeuronX Distributed Inference (NxDI)**를 사용하여 [**Llama3.1 70B Instruct**](https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct) 모델을 서빙하는 방법을 설명합니다.

AWS Neuron 공식문서의 [Llama 3.3 70B 가이드](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/libraries/nxd-inference/tutorials/trn2-llama3.3-70b-tutorial.html)를 기반으로 Llama 3.1 70B에 맞게 구성되었습니다.

**모델 정보:**
- **모델**: meta-llama/Llama-3.1-70B-Instruct
- **파라미터**: 70B
- **라이선스**: Llama 3.1 Community License (Gated Model)
- **컨텍스트 길이**: 최대 128K (실제 사용은 하드웨어 제약)

**⚠️ 중요: 사용된 인스턴스**
- Llama 3.1 70B는 약 140GB 모델로 **trn2.48xlarge (64 NeuronCores) 에서 진행**
- trn2.48xlarge는 64개 논리 코어 (4 NeuronCores × 16)

## ✅ Prerequisites (사전 준비)

진행하기 전에 다음 사항들을 확인하세요.

1. **인스턴스 실행:** `trn2.48xlarge` (64 NeuronCores) 인스턴스가 활성화(`Running`) 상태여야 합니다.

2. **DLAMI 사용:** Hugging Face Neuron Deep Learning AMI 또는 AWS Deep Learning AMI (Neuron) 권장
   * Neuron SDK 2.27.1 이상 필요
   * vLLM 0.13 Neuron 가상환경 포함

3. **Hugging Face 인증:**
   * Llama3.1은 Gated Model이므로 액세스 권한 필요
   * https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct 에서 액세스 요청

4. **(선택 사항) 고속 스토리지 설정:**
   * 모델 다운로드 및 캐시 속도를 높이려면 로컬 NVMe SSD (RAID 0) 사용을 고려할 수 있습니다.

## 1. 🚀 환경 설정

### Step 1-1: 가상환경 활성화

DLAMI에는 사전 구성된 vLLM 0.13 Neuron 가상환경이 포함되어 있습니다.

```bash
# vLLM 0.13 Neuron 추론 환경 활성화
source /opt/aws_neuronx_venv_pytorch_inference_vllm_0_13/bin/activate
```

**환경 확인:**
```bash
# Python 버전 확인
python --version

# 설치된 패키지 확인
pip list | grep -E "neuronx|vllm|transformers"

# vLLM 버전 확인
vllm --version
```

**Test 환경:**
- Python 3.12.3
- libneuronxla                      2.2.14584.0+06ac23d1
- neuronx-cc                        2.22.12471.0+b4a00d10
- neuronx-distributed               0.16.25997+f431c02e
- neuronx-distributed-inference     0.7.15063+bafa28d5
- torch-neuronx                     2.9.0.2.11.19912+e48cd891
- transformers                      4.56.2
- vllm                              0.13.0

### Step 1-2: Neuron SDK 버전 확인

```bash
# Neuron SDK 버전 확인
dpkg-query -W -f='${Version}\n' aws-neuronx-tools

# NeuronCore 확인
neuron-ls
```

**trn2.48xlarge 출력 예시:**
```
+--------+--------+----------+--------+
| NEURON | NEURON |  NEURON  | NEURON |
| DEVICE | CORES  | CORE IDS | MEMORY |
+--------+--------+----------+--------+
| 0      | 2      | 0-3      | 96 GB  |
| 1      | 2      | 4-7      | 96 GB  |
...
| 15     | 2      | 60-63    | 96 GB  |
+--------+--------+----------+--------+
```

### Step 1-3: Hugging Face 인증

```bash
# Hugging Face CLI 로그인
huggingface-cli login

# 토큰 입력 후 확인
huggingface-cli whoami
```

### Step 1-4: 모델 다운로드

모델을 원하는 위치에 미리 다운로드합니다.

```bash
# 모델 저장 디렉토리 생성
mkdir -p ~/models
cd ~/models

# Llama3.1 70B Instruct 모델 다운로드
huggingface-cli download meta-llama/Llama-3.1-70B-Instruct \
    --local-dir Llama-3.1-70B-Instruct

# 다운로드 확인
ls -lh Llama-3.1-70B-Instruct/
```

**예상 다운로드 크기:** ~140GB

**다운로드 시간:** 네트워크 속도에 따라 10-30분

## 2. 🔧 1단계: 모델 컴파일

`inference_demo` 도구를 사용하여 모델을 컴파일합니다. 이 과정은 첫 실행 시 1회만 수행하며, 컴파일된 모델은 재사용됩니다.

**🔄 실행 방법:**

이 가이드는 **권장 방법 (2단계 프로세스)**를 설명합니다:
1. **모델 컴파일** (첫 실행 시 1회, 20-50분 소요) - 명시적 컴파일로 디버깅 용이
2. **vLLM 서버 실행** (컴파일된 모델 재사용) - 빠른 재시작 (1-3분)

**💡 Quick Start (자동 컴파일):**

```bash
# 환경 변수 설정
export VLLM_NEURON_FRAMEWORK="neuronx-distributed-inference"

# vLLM 서버 실행 (첫 실행 시 자동 컴파일, 20-50분 소요)
python -m vllm.entrypoints.openai.api_server \
    --model /home/ubuntu/models/Llama-3.1-70B-Instruct \
    --tensor-parallel-size 64 \
    --max-num-seqs 1 \
    --max-model-len 16384 \
    --block-size 16 \
    --port 8000
```

**참고:**
- `--device neuron`은 vLLM 0.13에서 지원하지 않음 (자동 감지)
- 최적화 설정은 JSON 한 줄로 작성 (줄바꿈 없이)
- 컴파일된 모델은 자동으로 저장되어 재사용됨

하지만 **프로덕션 환경에서는 사전 컴파일을 강력히 권장**합니다:
- 컴파일 실패 시 디버깅 용이
- 서버 시작 시간 단축 (1-3분)
- 컴파일 로그 명확히 확인 가능
- AWS 공식 권장사항

## 요약

이 가이드를 통해 Llama 3.1 70B Instruct 모델을 AWS Trainium2에서 성공적으로 실행할 수 있습니다:
1. ✅ **환경 설정**: vLLM 0.13 Neuron 가상환경 활성화
2. ✅ **모델 다운로드**: Hugging Face에서 140GB 모델 다운로드
3. ✅ **서버 실행**: 통합된 명령어로 컴파일 및 서버 시작
4. ✅ **API 테스트**: OpenAI 호환 API로 추론 테스트

**핵심 포인트:**
- v1 플러그인 방식은 컴파일과 실행을 하나의 명령어로 통합
- `--override-neuron-config`를 통해 모든 최적화 옵션 전달
