!!! warning "Classic 가이드"
    이 문서는 NxD Inference (Maintenance Mode) 기반 가이드입니다.
    신규 배포는 [vLLM Neuron Plugin](../vllm/index.md)을 권장합니다.

# Serving Qwen3 8B Instruct on Trainium2 with vLLM + NxDI

이 가이드는 **AWS Trainium2 `trn2.48xlarge`** 인스턴스에서 **vLLM 0.13 + NeuronX Distributed Inference (NxDI)**를 사용하여 [**Qwen3 8B Instruct**](https://huggingface.co/Qwen/Qwen3-8B) 모델을 서빙하는 방법을 설명합니다.

**모델 정보:**
- **모델**: Qwen/Qwen3-8B
- **파라미터**: 8B
- **라이선스**: Apache 2.0 (Open Model)
- **컨텍스트 길이**: 최대 32K 

**⚠️ 중요: 사용된 인스턴스**
- Qwen3 8B는 약 16GB 모델로 **trn2.48xlarge (64 NeuronCores) 또는 더 작은 인스턴스에서 실행 가능**
- 이 가이드는 trn2.48xlarge 기준으로 작성되었습니다

**🔄 실행 방법:**
이 가이드에서는 두 가지 실행 방법을 설명합니다.
1.  **Quick Start (자동 컴파일):** 간단한 테스트를 위해 빠르게 서버를 시작하는 방법입니다.
2.  **권장 방법 (2단계 프로세스):** 모든 최적화 옵션을 적용하고 안정적으로 운영하기 위한 방법입니다.



## ✅ Prerequisites (사전 준비)

진행하기 전에 다음 사항들을 확인하세요.

1. **인스턴스 실행:** `trn2.48xlarge` 또는 더 작은 Trainium2 인스턴스가 활성화(`Running`) 상태여야 합니다.
   * 👉 **[가이드: EC2 인스턴스 실행](https://github.com/leesjpe/compute-foundation-on-aws/blob/main/ec2/ec2-dlami-neuron.md)**

2. **DLAMI 사용:** Hugging Face Neuron Deep Learning AMI 또는 AWS Deep Learning AMI (Neuron) 권장
   * Neuron SDK 2.27.1 에서 테스트하고 작성 됨
   * vLLM 0.13 Neuron 가상환경 포함

3. **Hugging Face 인증:**
   * Qwen3는 Open Model이므로 별도 액세스 권한 불필요
   * 하지만 다운로드 속도 향상을 위해 로그인 권장

4. **(선택 사항) 고속 스토리지 설정:**
   * 모델 다운로드 및 모델 컴파일, 캐시 속도를 높이려면 로컬 NVMe SSD (RAID 0) 사용을 고려할 수 있습니다.
   * 👉 **[가이드: 고속 스토리지 설정 (NVMe RAID 0)](https://github.com/leesjpe/compute-foundation-on-aws/blob/main/storage/local-nvme-setup.md)**



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

### Step 1-3: 모델 다운로드

모델을 원하는 위치에 미리 다운로드합니다.

```bash
# 모델 저장 디렉토리 생성
mkdir -p ~/models
cd ~/models

# Qwen3 8B Instruct 모델 다운로드
huggingface-cli download Qwen/Qwen3-8B \
    --local-dir Qwen3-8B

# 다운로드 확인
ls -lh Qwen3-8B/
```

**예상 다운로드 크기:** ~16GB

**다운로드된 파일 구조:**
```
Qwen3-8B/
├── config.json
├── generation_config.json
├── model-00001-of-00004.safetensors
├── model-00002-of-00004.safetensors
├── model-00003-of-00004.safetensors
├── model-00004-of-00004.safetensors
├── tokenizer.json
├── tokenizer_config.json
└── special_tokens_map.json
```

### 💡 Quick Start (자동 컴파일)

간단한 테스트를 위해 vLLM 서버가 자동으로 모델을 컴파일하도록 할 수 있습니다.

```bash
# 환경 변수 설정
export VLLM_NEURON_FRAMEWORK="neuronx-distributed-inference"

# vLLM 서버 실행 (첫 실행 시 자동 컴파일, 10-30분 소요)
python -m vllm.entrypoints.openai.api_server \
    --model /home/ubuntu/models/Qwen3-8B \
    --tensor-parallel-size 64 \
    --max-num-seqs 1 \
    --max-model-len 6400 \
    --block-size 16 \
    --port 8000
```

**프로덕션 환경에서는 사전 컴파일을 권장**합니다:
- 컴파일 실패 시 디버깅 용이
- 서버 시작 시간 단축 (1-3분)
- 컴파일 로그 명확히 확인 가능
- AWS 공식 권장사항

## 2. 🔧 모델 컴파일 (첫 실행 시 1회만)

Qwen3 8B를 Trainium2에서 실행하려면 먼저 모델을 컴파일해야 합니다. 이 과정은 첫 실행 시 1회만 수행하며, 컴파일된 모델은 재사용됩니다.

### Step 2-1: 컴파일 스크립트 생성

작업 디렉토리를 생성하고 컴파일 스크립트를 작성합니다.

```bash
# 작업 디렉토리 생성
mkdir -p ~/qwen3-8b-inference
cd ~/qwen3-8b-inference
```

**compile_model.sh:**
```bash
#!/bin/bash

# 모델 경로 설정
MODEL_PATH="/home/ubuntu/models/Qwen3-8B"
COMPILED_MODEL_PATH="/home/ubuntu/compiled_models/Qwen3-8B"

# 컴파일된 모델 저장 디렉토리 생성
mkdir -p $COMPILED_MODEL_PATH

# Neuron 런타임 설정
NUM_CORES=128      # trn2.48xlarge의 물리 코어 수
TP_DEGREE=32       # Tensor Parallelism degree (8B 모델은 32로 충분)
LNC=2              # Logical NeuronCore per physical core

export NEURON_RT_VIRTUAL_CORE_SIZE=$LNC
export NEURON_RT_NUM_CORES=$((NUM_CORES/NEURON_RT_VIRTUAL_CORE_SIZE))
export NEURON_RT_EXEC_TIMEOUT=600
export XLA_DENSE_GATHER_FACTOR=0
export NEURON_RT_INSPECT_ENABLE=0

echo "=========================================="
echo "Qwen3 8B Model Compilation"
echo "=========================================="
echo "Model path: $MODEL_PATH"
echo "Compiled model will be saved to: $COMPILED_MODEL_PATH"
echo "TP Degree: $TP_DEGREE"
echo "Max context length: 16384 tokens"
echo ""
echo "⏱️  This will take approximately 10-30 minutes on first run."
echo "=========================================="
echo ""
 
# 파이프라인의 첫 번째 명령어 실패 시 전체를 실패로 처리
set -o pipefail
 
# inference_demo를 사용한 모델 컴파일
if inference_demo \
    --model-type qwen3 \
    --task-type causal-lm \
        run \
        --model-path $MODEL_PATH \
        --compiled-model-path $COMPILED_MODEL_PATH \
        --torch-dtype bfloat16 \
        --start_rank_id 0 \
        --local_ranks_size $TP_DEGREE \
        --tp-degree $TP_DEGREE \
        --batch-size 2 \
        --max-context-length 4096 \
        --seq-len 8192 \
        --on-device-sampling \
        --top-k 1 \
        --do-sample \
        --sequence-parallel-enabled \
        --attn-kernel-enabled \
        --mlp-kernel-enabled \
        --cc-pipeline-tiling-factor 1 \
        --pad-token-id 151643 \
        --enable-bucketing \
        --context-encoding-buckets 128 256 512 1024 2048 4096 \
        --token-generation-buckets 128 256 512 1024 2048 4096 8192 \
        --prompt "What is AWS Trainium?" 2>&1 | tee compile.log; then
    
    echo ""
    echo "=========================================="
    echo "✅ Compilation successful!"
    echo "=========================================="
    echo "Compiled model saved to: $COMPILED_MODEL_PATH"
    echo "Compilation log saved to: compile.log"
    echo ""
else
    echo "" >&2
    echo "==========================================" >&2
    echo "❌ Compilation failed! Check log for details: compile.log" >&2
    echo "==========================================" >&2
fi
```


### Step 2-2: 컴파일 실행

```bash
# 실행 권한 부여
chmod +x compile_model.sh

# 컴파일 시작
./compile_model.sh
```

**⏱️ 예상 소요 시간:**
- 첫 실행: 10-30분 
- 컴파일 완료 후 모델은 `~/compiled_models/Qwen3-8B/`에 저장됩니다

### Step 2-3: 컴파일 성공 확인

```bash
# 컴파일된 모델 확인
ls -lh ~/compiled_models/Qwen3-8B/

# 컴파일 로그 확인
tail -50 compile.log
```

**성공 시 출력 예시:**
```
✅ Compilation complete!
Compiled model saved to: /home/ubuntu/compiled_models/Qwen3-8B/
```



## 3. 🌐 vLLM API 서버 실행

컴파일이 완료되면 vLLM 서버를 실행하여 OpenAI 호환 API를 제공할 수 있습니다.

### Step 3-1: 서버 시작 스크립트 생성

**start_vllm.sh:**
```bash
#!/bin/bash

# Neuron 런타임 설정
export NEURON_RT_INSPECT_ENABLE=0
export NEURON_RT_VIRTUAL_CORE_SIZE=2

# 모델 경로 설정 (컴파일 시 사용한 경로와 동일해야 함)
MODEL_PATH="/home/ubuntu/models/Qwen3-8B"
COMPILED_MODEL_PATH="/home/ubuntu/compiled_models/Qwen3-8B"

# vLLM 환경 변수 설정
export VLLM_NEURON_FRAMEWORK="neuronx-distributed-inference"
export NEURON_COMPILED_ARTIFACTS=$COMPILED_MODEL_PATH

echo "=========================================="
echo "Starting vLLM Server"
echo "=========================================="
echo "Model path: $MODEL_PATH"
echo "Compiled artifacts: $NEURON_COMPILED_ARTIFACTS"
echo "Port: 8000"
echo "Max model length: 16896 tokens"
echo "Max concurrent requests: 2"
echo "=========================================="
echo ""

# vLLM 서버 실행
VLLM_RPC_TIMEOUT=100000 python -m vllm.entrypoints.openai.api_server \
    --model $MODEL_PATH \
    --max-num-seqs 2 \
    --max-model-len 8192 \
    --tensor-parallel-size 32 \
    --block-size 16 \
    --port 8000 2>&1 | tee vllm_server.log &

PID=$!
echo "✅ vLLM server started with PID $PID"
echo "📝 Server logs are being saved to: vllm_server.log"
echo ""
echo "Wait 1-3 minutes for the server to fully load the model..."
echo "Check server status: curl http://localhost:8000/health"
```

### Step 3-2: 서버 실행

```bash
# 실행 권한 부여
chmod +x start_vllm.sh

# 서버 시작
./start_vllm.sh
```

**⏱️ 서버 시작 시간:**
- 컴파일된 모델 로딩: 1-3분
- 첫 요청 처리 시 워밍업: 5-15초

### Step 3-3: **⚠️ 중요: 파라미터 설명**
- `--max-model-len` = 컴파일 시 `--seq-len`
- `--max-num-seqs` = 컴파일 시 `--batch-size`
- `--tensor-parallel-size` = 컴파일 시 `--tp-degree`

### Step 3-4: 서버 상태 확인

```bash
# Health check
curl http://localhost:8000/health

# 모델 목록 확인
curl http://localhost:8000/v1/models

# 서버 로그 확인
tail -f vllm_server.log
```

**성공 시 출력:**
```json
{"status":"ok"}
```

**모델 이름 확인:**
```json
{
  "object": "list",
  "data": [{
    "id": "/home/ubuntu/models/Qwen3-8B",
    "object": "model",
    "created": 1770644707,
    "owned_by": "vllm"
  }]
}
```


---

## 4. 🧪 API 테스트

서버가 실행되면 OpenAI 호환 API로 테스트할 수 있습니다.

### Step 4-1: cURL 테스트

```bash
# Completion API 테스트
curl http://localhost:8000/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "/home/ubuntu/models/Qwen3-8B",
        "prompt": "Explain quantum computing in simple terms:",
        "max_tokens": 256,
        "temperature": 0.7
    }'
```

### Step 4-2: Python 클라이언트

**test_client.py:**
```python
from openai import OpenAI

# vLLM 서버에 연결
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"  # vLLM은 API 키 불필요
)

# 서버에서 사용 가능한 모델 확인
models = client.models.list()
model_name = models.data[0].id
print(f"Using model: {model_name}")

# Completion API
response = client.completions.create(
    model=model_name,
    prompt="The future of AI is",
    max_tokens=256,
    temperature=0.7
)
print("\n=== Completion ===")
print(response.choices[0].text)

# Chat API
response = client.chat.completions.create(
    model=model_name,
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is AWS Trainium?"}
    ],
    max_tokens=256,
    temperature=0.7
)
print("\n=== Chat ===")
print(response.choices[0].message.content)
```

### Step 4-3: 스트리밍 응답 테스트

**test_streaming.py:**
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"
)

# 스트리밍 Chat API
stream = client.chat.completions.create(
    model="/home/ubuntu/models/Qwen3-8B",
    messages=[
        {"role": "user", "content": "Write a short story about AI."}
    ],
    max_tokens=512,
    temperature=0.7,
    stream=True
)

print("=== Streaming Response ===")
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
print()
```



## 5. 💡 추가 팁

### 모니터링

실시간 NeuronCore 사용률 확인:

```bash
# 실시간 모니터링
neuron-top

# 상세 정보
neuron-monitor

# 특정 프로세스 모니터링
watch -n 1 neuron-ls
```

### 컴파일 캐시 재사용

컴파일된 모델은 자동으로 저장되어 재사용됩니다:

```bash
# 컴파일된 모델 위치
ls -lh ~/compiled_models/Qwen3-8B/

# 컴파일된 모델 크기 확인
du -sh ~/compiled_models/Qwen3-8B/
```

**재사용 조건:**
- 동일한 `--compiled-model-path` 사용
- 동일한 컴파일 파라미터 (tp-degree, batch-size, max-context-length 등)
- `NEURON_COMPILED_ARTIFACTS` 환경 변수 설정

### 다른 저장 위치 사용

NVMe 또는 다른 위치에 모델을 저장하려면:

```bash
# NVMe에 다운로드 (예시)
mkdir -p /data/models
huggingface-cli download Qwen/Qwen3-8B \
    --local-dir /data/models/Qwen3-8B \
    --local-dir-use-symlinks False

# 컴파일된 모델도 NVMe에 저장
mkdir -p /data/compiled_models

# 스크립트에서 경로 변경
MODEL_PATH="/data/models/Qwen3-8B/"
COMPILED_MODEL_PATH="/data/compiled_models/Qwen3-8B/"
```

### 로그 레벨 조정

디버깅 시 로그 레벨 조정:

```bash
# Neuron 런타임 로그
export NEURON_RT_LOG_LEVEL=INFO

# 더 상세한 디버그 정보
export NEURON_RT_LOG_LEVEL=DEBUG
export NEURON_RT_INSPECT_ENABLE=1
```

### 백그라운드 실행

서버를 백그라운드에서 실행:

```bash
# nohup으로 백그라운드 실행
nohup ./start_vllm.sh > vllm_server.log 2>&1 &

# 프로세스 확인
ps aux | grep vllm

# 로그 확인
tail -f vllm_server.log

# 서버 종료
pkill -f "vllm.entrypoints.openai.api_server"
```


---

## 요약

이 가이드를 통해 Qwen3 8B Instruct 모델을 AWS Trainium2에서 성공적으로 실행할 수 있습니다:

1. ✅ **환경 설정**: vLLM 0.13 Neuron 가상환경 활성화
2. ✅ **모델 다운로드**: Hugging Face에서 16GB 모델 다운로드
3. ✅ **모델 컴파일**: inference_demo로 10-30분 컴파일
4. ✅ **서버 실행**: 컴파일된 모델로 vLLM API 서버 시작
5. ✅ **API 테스트**: OpenAI 호환 API로 추론 테스트

**문제 발생 시:**
- 서버 로그 확인 (`tail -f vllm_server.log`)
- NeuronCore 모니터링 (`neuron-top`)
- 컴파일 로그 확인 (`tail -f compile.log`)

**다음 단계:**
- 성능 최적화: TP degree, batch size, context length 조정
- 프로덕션 배포: 로드 밸런서, 오토스케일링 설정