# vLLM Neuron 모델 온보딩 가이드

> 신규 모델 아키텍처를 vLLM Neuron Plugin에 추가하여 AWS AI Chip 에서 서빙하기 위한 전체 프로세스를 다룹니다.



## 온보딩의 본질: 2-Phase 접근

### Phase 1: NF 함수로 모델 "교체" (필수)

- `NF.flash_attention`, `NF.mlp` 등 Plugin 빌딩블록 사용
- **이것만으로도 NKI 최적화가 자동 적용됩니다.** (NF 내부에 이미 NKI 커널 내장)
- 목표: 정확하게 동작하는 모델

### Phase 2: 커스텀 NKI 커널 추가 (선택, 성능 최적화)

- NF 기본 함수로 커버 안 되는 부분에 직접 NKI 커널 투입
- 예: Gemma4 `attention_cte` → ≤16k TTFT 40% 개선
- 목표: 경쟁력 있는 성능



## 전체 흐름 (5단계)

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ 1. Implement    2. Register      3. Compile &    4. Validate    5. Benchmark  │
│ (config/model/   (ModelRegistry)   Smoke Test     Accuracy       & Tune       │
│  factory/weights)                                                             │
└───────────────────────────────────────────────────────────────────────────────┘
```


## Step 0: 아키텍처 Diff 분석

온보딩 전 필수 작업 — 내 모델이 기존 Reference 구현(Llama)과 어디가 다른지 파악합니다.

!!! info "모델링 코드 위치"
    HuggingFace Hub의 모델 레포에는 weight + config.json + tokenizer만 존재합니다.
    모델링 로직(forward 구현)은 `transformers` 패키지 안에 있습니다:
    `transformers/models/{model_name}/modeling_{model_name}.py`

### 분석 스크립트

임의의 두 모델을 비교할 수 있습니다 (`MODEL_A`, `MODEL_B`만 변경):

```bash
pip install transformers torch
# Gated 모델(Llama 등)은 사전에 허깅페이스 로그인: $hf auth login
```

```python
#!/usr/bin/env python3
"""
vLLM Neuron 모델 온보딩 — Step 0: 아키텍처 Diff 분석
임의의 두 모델 비교 가능 (MODEL_A, MODEL_B만 변경)

사용법: python3 arch_diff_analysis.py
필요: pip install transformers torch (weight 다운로드 없음, config만 fetch)
"""

import json
import torch
from transformers import AutoConfig, AutoModelForCausalLM

MODEL_A = "meta-llama/Llama-3.1-8B"
MODEL_B = "google/gemma-4-31B-it"

print("=" * 80)
print("  1. config.json 비교")
print("=" * 80)

config_a = AutoConfig.from_pretrained(MODEL_A)
config_b = AutoConfig.from_pretrained(MODEL_B)

dict_a = config_a.to_dict()
dict_b = config_b.to_dict()

all_keys = sorted(set(list(dict_a.keys()) + list(dict_b.keys())))

print(f"\n{'Key':<40} {MODEL_A:<30} {MODEL_B:<30}")
print("-" * 100)

only_a = []
only_b = []
different = []

for key in all_keys:
    if key in ['_name_or_path', 'transformers_version', 'tokenizer_class', '_attn_implementation_autoset']:
        continue

    val_a = dict_a.get(key, "—")
    val_b = dict_b.get(key, "—")

    if val_a == "—":
        only_b.append((key, val_b))
    elif val_b == "—":
        only_a.append((key, val_a))
    elif val_a != val_b:
        different.append((key, val_a, val_b))

print("\n### 값이 다른 필드 ###")
for key, va, vb in different:
    print(f"  {key:<38} {str(va)[:28]:<30} {str(vb)[:28]}")

print(f"\n### {MODEL_B}에만 있는 필드 ({len(only_b)}개) ###")
for key, val in only_b[:20]:
    print(f"  {key:<38} = {str(val)[:50]}")

print(f"\n### {MODEL_A}에만 있는 필드 ({len(only_a)}개) ###")
for key, val in only_a[:20]:
    print(f"  {key:<38} = {str(val)[:50]}")


print("\n\n")
print("=" * 80)
print("  2. 모델 구조 출력 (weight 로드 없음, 메모리 0)")
print("=" * 80)

print(f"\n### {MODEL_A} 구조 ###\n")
try:
    with torch.device("meta"):
        model_a = AutoModelForCausalLM.from_config(config_a)
    model_str = str(model_a)
    lines = model_str.split('\n')
    for line in lines[:60]:
        print(f"  {line}")
    if len(lines) > 60:
        print(f"  ... ({len(lines) - 60} more lines)")
    del model_a
except Exception as e:
    print(f"  [ERROR] {e}")

print(f"\n### {MODEL_B} 구조 ###\n")
try:
    with torch.device("meta"):
        model_b = AutoModelForCausalLM.from_config(config_b)
    model_str = str(model_b)
    lines = model_str.split('\n')
    for line in lines[:60]:
        print(f"  {line}")
    if len(lines) > 60:
        print(f"  ... ({len(lines) - 60} more lines)")
    del model_b
except Exception as e:
    print(f"  [ERROR] {e}")

```

### Diff 결과 해석

스크립트 결과가 나오면, 아래 체크리스트로 온보딩 작업 항목을 도출합니다:

| # | 비교 항목 | config에서 보이는 필드 | 다르면 영향받는 코드 |
|---|-----------|---|---|
| 1 | **Attention 방식** | `num_attention_heads`, `num_key_value_heads`, `layer_types`, `sliding_window` | `model.py` — attention forward 전체 |
| 2 | **Heterogeneous Layers** | `per_layer_config`, `layer_types` 배열 | `model.py` — 레이어별 분기, weight 초기화 |
| 3 | **Position Encoding** | `rope_theta`, `rope_scaling`, `rope_parameters`, `partial_rotary_factor` | `model.py` — RoPE 계산 로직 |
| 4 | **MLP/Activation** | `hidden_act`, `hidden_activation`, `intermediate_size` | NF.mlp 호환 확인, 안 맞으면 직접 구현 |
| 5 | **Normalization** | `rms_norm_eps` + modeling 소스 확인 | 위치/타입(RMS vs Layer) 차이 |
| 6 | **Config 구조** | top-level fields vs `text_config`/`vision_config` nested | `config.py` — from_configs() 파싱 로직 |
| 7 | **Embedding** | `tie_word_embeddings`, `vocab_size` | weight sharing 로직, vocab 크기 |
| 8 | **Special features** | `final_logit_softcapping`, `enable_moe_block`, `vision_config` | 추가 구현 필요 여부 |



## Stage 1: Implement (모델 구현)

### 디렉토리 구조

```
src/model/your_model/
├── __init__.py
├── config.py       # HuggingFace PretrainedConfig → 자체 dataclass
├── factory.py      # vLLM ModelRegistry 인터페이스
└── model.py        # 전체 모델 구현 (Attention, MLP, Embedding, LMHead)
```

### 핵심 구현 요소

| 파일 | 역할 | 핵심 |
|------|------|------|
| `config.py` | HF config 파싱 | `from_configs(hf_config, neuron_config)` classmethod |
| `model.py` | 실제 모델 | forward(), get_kv_spec(), bind_kv_cache(), load_weights(), from_configs() |
| `factory.py` | 팩토리 패턴 | variant 선택 (BF16 vs quantized), config 검증 |

### 사용 가능한 Building Blocks

| Component | Utility |
|-----------|---------|
| Attention | `NF.qkv_proj`, `NF.flash_attention`, `NF.segmented_attention`, `NF.attention_decode`, `NF.o_proj` |
| MLP | `NF.mlp` — fused gate/up/down + NKI kernel |
| Embedding | `vllm_neuron.nn.VocabDimShardedEmbedding` |
| LM Head | `vllm_neuron.nn.ColumnParallelLinear` |
| Weight Loading | `sharding_weight_loader`, `fused_qkv_weight_loader`, `with_rank_override`, EP loaders |
| KV Cache | `KVSpec`, `LayerSpec` dataclasses |
| Collectives | `get_tp_group()` → all_gather, reduce_scatter, all_reduce |



!!! info "NF (vllm_neuron.functional) 소스 코드"
    [vllm_neuron/functional](https://github.com/vllm-project/vllm-neuron/tree/release-0.24.0.1.1.0/vllm_neuron/functional) — Neuron HW에서는 NKI 커널로 dispatch되고, CPU에서는 PyTorch fallback으로 동작합니다. 새 모델 구현 시 이 함수들의 입출력 shape과 지원 파라미터를 소스에서 직접 확인하세요.

!!! tip "Reference 구현"
    - Dense model → `vllm_neuron/model/llama3/` (porting template)
    - MoE model → `vllm_neuron/model/gpt_oss/` (expert parallel)




## Stage 2: Register (모델 등록)

```python
from vllm import ModelRegistry
from .factory import MyCustomModelForCausalLM

ModelRegistry.register_model(
    "MyCustomModelForCausalLM",   # ← HF config.json의 "architectures" 필드와 일치
    MyCustomModelForCausalLM
)
```


## Stage 3: Compile & Smoke Test

```python
from vllm import LLM, SamplingParams

llm = LLM(model="/path/to/model", max_num_seqs=4, max_model_len=2048, tensor_parallel_size=8)
output = llm.generate(["Hello, my name is"], SamplingParams(max_tokens=32, temperature=0.0))
print(output[0].outputs[0].text)
```

- 첫 실행 시 모든 bucket에 대해 NEFF 컴파일 (수 분~수십 분)
- CPU Compile Mode: `VLLM_NEURON_CPU_COMPILE=1 NEURON_PLATFORM_TARGET_OVERRIDE=trn2` → HW 없이 NEFF 사전 생성



## Stage 4: Validate Accuracy

### 3-Level 검증 프레임워크

| Level | 대상 | 방법 | Pass 기준 |
|-------|------|------|-----------|
| **L1: Task-level** | 전체 모델 | lm_eval, longbench | 사용자 정의 threshold |
| **L2: Prompt-level** | 토큰 단위 | teacher-forcing logit 비교 (HF FP32 vs BF16 vs Neuron) | divergence tolerance + KV BC ≥ 0.99 |
| **L3: Module-level** | 개별 컴포넌트 | attention/MLP/RMSNorm 단위 테스트 | HF reference 텐서 매치 |

### Three-Way Comparison

```python
from vllm_neuron.accuracy.testing import assert_close_three_way

assert_close_three_way(
    target=neuron_output,       # 테스트 대상
    expected=hf_fp32_output,    # 금본위 (FP32)
    baseline=hf_bf16_output,    # BF16 수치 오차 기준
    rtol=0.01, name="attn_prefill",
)
```

**해석**: Neuron 오차 ≈ BF16 오차 → 정상. Neuron 오차 >> BF16 → 버그.



## Stage 5: Benchmark & Tune

```bash
vllm serve /path/to/model --tensor-parallel-size 8 --max-num-seqs 32
vllm bench serve --model /path/to/model --dataset-name random \
    --random-input-len 1024 --random-output-len 128 --num-prompts 100
```

### Key Tuning Parameters

| Parameter | 효과 |
|-----------|------|
| `num_batched_tokens_buckets` | Prefill bucket 수 |
| `num_seqs_buckets` | Decode bucket 수 |
| `attention_dp_size` / `mlp_dp_size` | Data parallelism |
| `ep_degree` | Expert parallelism (MoE) |
| On-device sampling | CPU↔NC 왕복 제거 |
| FP8 KV cache | 메모리 절감 → 더 큰 batch |



## Phase 2 상세: NKI 커널 적용 경로

NF 함수로 충분하지 않을 때, 추가 NKI 커널을 적용하는 순서:

```
1. nkilib에서 기존 커널 검색 (from nkilib.core.attention import attention_cte 등)
2. 맞는 커널이 있으면 → wrap_nki()로 감싸서 model.py에서 호출
3. 없으면 → @nki.jit으로 직접 커널 작성 후 동일하게 wrap_nki()
```

### vLLM Plugin 내 NKI 실행 경로

```
model.py forward() 호출
  → torch.compile (전체 forward를 graph로 캡처)
    → Neuron Graph Compiler가 그래프 컴파일
      → NKI 커널 부분: wrap_nki() → NKI Compiler가 별도 컴파일
      → 나머지 부분: Graph Compiler가 자동 최적화
    → 결과: 하나의 NEFF 바이너리 안에 두 컴파일러 결과가 공존
```

### NKI 커널 등록 방법 비교

| | PyTorch Native (연구/학습용) | vLLM Plugin (서빙/프로덕션) |
|---|---|---|
| **커널 정의** | `@nki.jit` | `@nki.jit` (동일) |
| **PyTorch 연동** | `@nki_op` + `wrap_nki` → custom op 등록 | `wrap_nki()` → Plugin HOP dispatch |
| **컴파일 단위** | op별 또는 torch.compile graph | 전체 forward를 단일 NEFF로 |
| **필요 환경** | PyTorch Native Beta (torch-neuronx) | vLLM Neuron Plugin (Beta 불필요) |

### 코드 예시

```python
# 1. NKI 커널 정의
@nki.jit
def my_custom_attention(q_ref, k_ref, v_ref, ...):
    q = nl.load(q_ref[...])
    # ... SBUF 연산 ...
    nl.store(out_ref[...], result)

# 2. vLLM Plugin에서 등록
from vllm_neuron.utils.nki_utils import wrap_nki
wrapped_attn = wrap_nki(my_custom_attention)

# 3. model.py에서 호출
def forward_prefill(self, q, k, v, ...):
    return wrapped_attn[grid](q, k, v, ...)
```



## 참고 자료

- [공식 문서: How to onboard a model to vLLM Neuron](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/vllm-neuron/docs/model-dev/onboarding-models.html)
- [공식 문서: Debugging accuracy issues](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/vllm-neuron/docs/model-dev/accuracy-debugging-guide.html)
- [GitHub: vllm-neuron](https://github.com/vllm-project/vllm-neuron)
- [참고 구현: Gemma4-31B on Trainium2](https://github.com/arminagha1234/Armin-Neuron/tree/main/gemma4-31b/vllm-neuron-Public_Final)
