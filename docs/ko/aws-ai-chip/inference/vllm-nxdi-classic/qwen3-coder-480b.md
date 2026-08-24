!!! warning "Classic 가이드"
    이 문서는 NxD Inference (Maintenance Mode) 기반 가이드입니다.
    신규 배포는 [vLLM Neuron Plugin](../vllm/index.md)을 권장합니다.

# Qwen3-Coder-480B Inference on AWS Trainium2 (Trn2) with vLLM

이 가이드는 **AWS Trainium2 (Trn2)** 인스턴스에서 **vLLM**을 사용하여 [Qwen3-Coder-480B-A35B-Instruct](https://huggingface.co/Qwen/Qwen3-Coder-480B-A35B-Instruct) 모델을 서빙하고 추론하는 방법을 설명합니다.

본 가이드는 MoE(Mixture of Experts) 아키텍처를 지원하며, Neuron SDK에 최적화된 설정을 포함하고 있습니다.

## 📋 사전 준비 (Prerequisites)

이 가이드를 실행하기 전에 **EC2 인스턴스 생성 및 스토리지 설정**이 완료되어야 합니다.
대용량 모델(480B)을 다루기 위해 고성능 스토리지 구성을 권장합니다.

- **[EC2 인스턴스 생성](https://github.com/leesjpe/compute-foundation-on-aws/blob/main/ec2/ec2-dlami-neuron.md) 및 [고성능 스토리지(RAID 0) 마운트](https://github.com/leesjpe/compute-foundation-on-aws/blob/main/storage/local-nvme-setup.md) 방법** 
- **권장 인스턴스:** `trn2.48xlarge`
- **필수 스토리지:** `/data` 경로에 최소 4TB 이상의 NVMe/EBS 볼륨 마운트

---

## 🛠️ 1. 환경 설정 및 종속성 확인

AWS Neuron vLLM 가상 환경을 활성화하고 버전을 확인합니다.

```bash
# 가상 환경 활성화
source /opt/aws_neuronx_venv_pytorch_inference_vllm_0_13/bin/activate

# 주요 패키지 버전 확인
pip list | grep neuron
```

### ✅ Tested Environment Versions
본 가이드는 아래 버전에서 Test 되었습니다.

```
pip list | grep neuron
```

| Package Name | Version |
| :--- | :--- |
| `libneuronxla` | `2.2.14584.0+06ac23d1` |
| `neuronx-cc` | `2.22.12471.0+b4a00d10` |
| `neuronx-distributed` | `0.16.25997+f431c02e` |
| `neuronx-distributed-inference` | `0.7.15063+bafa28d5` |
| `torch-neuronx` | `2.9.0.2.11.19912+e48cd891` |
| `vllm-neuron` | `0.3.0` |

---

## 📥 2. 모델 다운로드

Hugging Face CLI를 사용하여 모델을 `/data` 디렉터리에 다운로드합니다.
다운로드 과정을 터미널에서 직접 모니터링하기 위해 포그라운드에서 실행합니다.

> **Note:** 모델 크기가 매우 크므로(약 1TB), 다운로드에 상당한 시간이 소요될 수 있습니다.

```bash
# 1. 저장소 권한 설정 (/data 경로)
sudo chown -R ubuntu:ubuntu /data
mkdir -p /data/models/qwen3-coder-480b-a35b-instruct

# 2. 모델 다운로드 실행
# --local-dir-use-symlinks False: 캐시가 아닌 실제 파일을 해당 경로에 저장합니다.
huggingface-cli download Qwen/Qwen3-Coder-480B-A35B-Instruct \
--local-dir /data/models/qwen3-coder-480b-a35b-instruct \
--local-dir-use-symlinks False
```

---

## 🚀 3. vLLM 서버 실행 (Server Serving)

Neuron SDK에 최적화된 설정을 적용하여 API 서버를 실행합니다.
Qwen3 MoE 모델을 위한 `additional-config`가 포함되어 있습니다.

> **Note:** 초기 실행 시 모델 컴파일(Compilation) 및 로딩으로 인해 서버가 준비(`Uvicorn running...`)될 때까지 수십 분이 소요될 수 있습니다.

```bash
VLLM_NEURON_FRAMEWORK='neuronx-distributed-inference' python -m vllm.entrypoints.openai.api_server \
  --model="/data/models/qwen3-coder-480b-a35b-instruct" \
  --tensor-parallel-size=64 \
  --max-num-seqs=1 \
  --max-model-len=16384 \
  --additional-config='{"override_neuron_config": {
    "async_mode": false,
    "attn_kernel_enabled": false,
    "batch_size": 1,
    "cc_pipeline_tiling_factor": 1,
    "context_encoding_buckets": [16384],
    "cp_degree": 1,
    "ctx_batch_size": 1,
    "enable_bucketing": true,
    "flash_decoding_enabled": false,
    "fused_qkv": false,
    "is_continuous_batching": true,
    "logical_nc_config": 2,
    "max_context_length": 16384,
    "moe_ep_degree": 1,
    "moe_tp_degree": 64,
    "on_device_sampling_config": {
      "do_sample": true,
      "temperature": 0.6,
      "top_k": 20,
      "top_p": 0.95
    },
    "qkv_cte_nki_kernel_fuse_rope": false,
    "qkv_kernel_enabled": false,
    "qkv_nki_kernel_enabled": false,
    "seq_len": 16384,
    "sequence_parallel_enabled": true,
    "token_generation_buckets": [16384],
    "torch_dtype": "bfloat16",
    "tp_degree": 64
  }}' \
  --no-enable-chunked-prefill \
  --no-enable-prefix-caching \
  --port=8000
```

<img width="1067" height="801" alt="Screenshot 2026-01-28 at 10 39 59 AM" src="https://github.com/user-attachments/assets/4cc59b6f-5351-4222-9bda-12fdc26a72e6" />



---

## 🧪 4. 추론 테스트 (Tool Calling Demo)

서버가 정상적으로 실행되면 아래 Python 스크립트를 통해 Tool Calling 기능을 테스트합니다.
vLLM 서버 옵션 제약 없이 **프롬프트 엔지니어링(System Prompt)** 방식을 사용하여 JSON 출력을 유도합니다.

### `test_inference.py` 작성

```python
from openai import OpenAI
import json

# 1. 클라이언트 설정
client = OpenAI(
    base_url='http://localhost:8000/v1', 
    api_key="EMPTY"
)

# 2. 도구(Tools) 정의를 '텍스트 프롬프트'로 변환
# API의 tools 파라미터를 쓰면 서버 설정 충돌 가능성이 있어 System Prompt로 주입합니다.
system_instruction = """
You are a helpful assistant. You have access to the following tools:

{
  "name": "square_the_number",
  "description": "output the square of the number.",
  "parameters": {
      "input_num": {"type": "number", "description": "The number to square"}
  }
}

If the user asks something that requires a tool, DO NOT generate plain text.
Instead, output a JSON object specifically formatted like this:
{"tool_uses": [{"name": "square_the_number", "arguments": {"input_num": 123}}]}
"""

# 3. 요청 보내기
print("Thinking (Prompt Engineering Mode)...")

messages = [
    {'role': 'system', 'content': system_instruction},
    {'role': 'user', 'content': 'square the number 1024'}
]

completion = client.chat.completions.create(
    model="/data/models/qwen3-coder-480b-a35b-instruct", # 서버 실행 시 지정한 모델 경로
    messages=messages,
    # ★ 중요: tools 파라미터를 삭제하고 Prompt로 제어
    max_tokens=1024,
    temperature=0.0, 
)

# 4. 결과 확인 및 파싱
response_text = completion.choices[0].message.content
print(f"▼ 모델 응답 (Raw Text):")
print(response_text)

# JSON으로 파싱 시도 (모델이 의도대로 응답했는지 검증)
try:
    if "{" in response_text:
        # JSON 부분만 추출
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        tool_call_json = json.loads(response_text[json_start:json_end])
        
        print("\n▼ 성공! 모델이 도구 호출 JSON을 생성했습니다:")
        print(json.dumps(tool_call_json, indent=2))
    else:
        print("\n▼ 모델이 JSON을 생성하지 않았습니다.")
except Exception as e:
    print(f"\n▼ 파싱 에러: {e}")
```

### 테스트 실행

```bash
python3 test_inference.py
```
<img width="800" height="906" alt="Screenshot 2026-01-28 at 10 43 13 AM" src="https://github.com/user-attachments/assets/ff42a804-713b-4738-a602-2032c03cf736" />



---

## 📝 Appendix: 