# vLLM Neuron Model Onboarding Guide

> This covers the full process of adding a new model architecture to the vLLM Neuron Plugin and serving it on AWS AI Chips.



## The essence of onboarding: a 2-phase approach

### Phase 1: "Replace" the model with NF functions (required)

- Use Plugin building blocks such as `NF.flash_attention` and `NF.mlp`
- **This alone applies NKI optimizations automatically.** (NF already has NKI kernels built in)
- Goal: a model that works correctly

### Phase 2: Add custom NKI kernels (optional, performance optimization)

- Apply NKI kernels directly where the default NF functions don't cover
- Example: Gemma4 `attention_cte` → 40% TTFT improvement at ≤16k
- Goal: competitive performance



## Overall flow (5 stages)

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ 1. Implement    2. Register      3. Compile &    4. Validate    5. Benchmark  │
│ (config/model/   (ModelRegistry)   Smoke Test     Accuracy       & Tune       │
│  factory/weights)                                                             │
└───────────────────────────────────────────────────────────────────────────────┘
```


## Step 0: Architecture diff analysis

A required task before onboarding — identify where your model differs from the existing reference implementation (Llama).

!!! info "Where the modeling code lives"
    A model repo on the HuggingFace Hub contains only weights + config.json + tokenizer.
    The modeling logic (the forward implementation) lives in the `transformers` package:
    `transformers/models/{model_name}/modeling_{model_name}.py`

### Analysis script

You can compare any two models (just change `MODEL_A` and `MODEL_B`):

```bash
pip install transformers torch
# For gated models (Llama, etc.), log in to Hugging Face beforehand: $hf auth login
```

```python
#!/usr/bin/env python3
"""
vLLM Neuron model onboarding — Step 0: Architecture diff analysis
Can compare any two models (just change MODEL_A, MODEL_B)

Usage: python3 arch_diff_analysis.py
Requires: pip install transformers torch (no weight download, fetches config only)
"""

import json
import torch
from transformers import AutoConfig, AutoModelForCausalLM

MODEL_A = "meta-llama/Llama-3.1-8B"
MODEL_B = "google/gemma-4-31B-it"

print("=" * 80)
print("  1. config.json comparison")
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

print("\n### Fields with different values ###")
for key, va, vb in different:
    print(f"  {key:<38} {str(va)[:28]:<30} {str(vb)[:28]}")

print(f"\n### Fields only in {MODEL_B} ({len(only_b)}) ###")
for key, val in only_b[:20]:
    print(f"  {key:<38} = {str(val)[:50]}")

print(f"\n### Fields only in {MODEL_A} ({len(only_a)}) ###")
for key, val in only_a[:20]:
    print(f"  {key:<38} = {str(val)[:50]}")


print("\n\n")
print("=" * 80)
print("  2. Model structure (no weight load, zero memory)")
print("=" * 80)

print(f"\n### {MODEL_A} structure ###\n")
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

print(f"\n### {MODEL_B} structure ###\n")
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

### Interpreting the diff results

Once you have the script output, use the checklist below to derive your onboarding work items:

| # | Comparison item | Fields visible in config | Code affected if different |
|---|-----------|---|---|
| 1 | **Attention method** | `num_attention_heads`, `num_key_value_heads`, `layer_types`, `sliding_window` | `model.py` — the entire attention forward |
| 2 | **Heterogeneous Layers** | `per_layer_config`, `layer_types` array | `model.py` — per-layer branching, weight initialization |
| 3 | **Position Encoding** | `rope_theta`, `rope_scaling`, `rope_parameters`, `partial_rotary_factor` | `model.py` — RoPE calculation logic |
| 4 | **MLP/Activation** | `hidden_act`, `hidden_activation`, `intermediate_size` | Check NF.mlp compatibility; implement manually if it doesn't match |
| 5 | **Normalization** | `rms_norm_eps` + check the modeling source | Differences in position/type (RMS vs Layer) |
| 6 | **Config structure** | top-level fields vs `text_config`/`vision_config` nested | `config.py` — from_configs() parsing logic |
| 7 | **Embedding** | `tie_word_embeddings`, `vocab_size` | weight sharing logic, vocab size |
| 8 | **Special features** | `final_logit_softcapping`, `enable_moe_block`, `vision_config` | Whether additional implementation is needed |



## Stage 1: Implement (model implementation)

### Directory structure

```
src/model/your_model/
├── __init__.py
├── config.py       # HuggingFace PretrainedConfig → your own dataclass
├── factory.py      # vLLM ModelRegistry interface
└── model.py        # full model implementation (Attention, MLP, Embedding, LMHead)
```

### Key implementation elements

| File | Role | Key points |
|------|------|------|
| `config.py` | HF config parsing | `from_configs(hf_config, neuron_config)` classmethod |
| `model.py` | the actual model | forward(), get_kv_spec(), bind_kv_cache(), load_weights(), from_configs() |
| `factory.py` | factory pattern | variant selection (BF16 vs quantized), config validation |

### Available Building Blocks

| Component | Utility |
|-----------|---------|
| Attention | `NF.qkv_proj`, `NF.flash_attention`, `NF.segmented_attention`, `NF.attention_decode`, `NF.o_proj` |
| MLP | `NF.mlp` — fused gate/up/down + NKI kernel |
| Embedding | `vllm_neuron.nn.VocabDimShardedEmbedding` |
| LM Head | `vllm_neuron.nn.ColumnParallelLinear` |
| Weight Loading | `sharding_weight_loader`, `fused_qkv_weight_loader`, `with_rank_override`, EP loaders |
| KV Cache | `KVSpec`, `LayerSpec` dataclasses |
| Collectives | `get_tp_group()` → all_gather, reduce_scatter, all_reduce |



!!! info "NF (vllm_neuron.functional) source code"
    [vllm_neuron/functional](https://github.com/vllm-project/vllm-neuron/tree/release-0.24.0.1.1.0/vllm_neuron/functional) — On Neuron hardware it dispatches to NKI kernels, and on CPU it works via a PyTorch fallback. When implementing a new model, check these functions' input/output shapes and supported parameters directly in the source.

!!! tip "Reference implementations"
    - Dense model → `vllm_neuron/model/llama3/` (porting template)
    - MoE model → `vllm_neuron/model/gpt_oss/` (expert parallel)




## Stage 2: Register (model registration)

```python
from vllm import ModelRegistry
from .factory import MyCustomModelForCausalLM

ModelRegistry.register_model(
    "MyCustomModelForCausalLM",   # ← matches the "architectures" field in HF config.json
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

- On the first run, NEFF is compiled for all buckets (minutes to tens of minutes)
- CPU Compile Mode: `VLLM_NEURON_CPU_COMPILE=1 NEURON_PLATFORM_TARGET_OVERRIDE=trn2` → pre-generate NEFF without hardware



## Stage 4: Validate Accuracy

### 3-level validation framework

| Level | Target | Method | Pass criteria |
|-------|------|------|-----------|
| **L1: Task-level** | the whole model | lm_eval, longbench | user-defined threshold |
| **L2: Prompt-level** | per token | teacher-forcing logit comparison (HF FP32 vs BF16 vs Neuron) | divergence tolerance + KV BC ≥ 0.99 |
| **L3: Module-level** | individual components | attention/MLP/RMSNorm unit tests | HF reference tensor match |

### Three-Way Comparison

```python
from vllm_neuron.accuracy.testing import assert_close_three_way

assert_close_three_way(
    target=neuron_output,       # the test target
    expected=hf_fp32_output,    # gold standard (FP32)
    baseline=hf_bf16_output,    # BF16 numerical-error baseline
    rtol=0.01, name="attn_prefill",
)
```

**Interpretation:** Neuron error ≈ BF16 error → normal. Neuron error >> BF16 → bug.



## Stage 5: Benchmark & Tune

```bash
vllm serve /path/to/model --tensor-parallel-size 8 --max-num-seqs 32
vllm bench serve --model /path/to/model --dataset-name random \
    --random-input-len 1024 --random-output-len 128 --num-prompts 100
```

### Key Tuning Parameters

| Parameter | Effect |
|-----------|------|
| `num_batched_tokens_buckets` | number of prefill buckets |
| `num_seqs_buckets` | number of decode buckets |
| `attention_dp_size` / `mlp_dp_size` | Data parallelism |
| `ep_degree` | Expert parallelism (MoE) |
| On-device sampling | eliminates CPU↔NC round trips |
| FP8 KV cache | memory savings → larger batches |



## Phase 2 detail: the path to applying NKI kernels

When NF functions aren't enough, the order for applying additional NKI kernels:

```
1. Search nkilib for an existing kernel (e.g., from nkilib.core.attention import attention_cte)
2. If a suitable kernel exists → wrap it with wrap_nki() and call it from model.py
3. If not → write the kernel yourself with @nki.jit, then wrap_nki() the same way
```

### NKI execution path inside the vLLM Plugin

```
model.py forward() call
  → torch.compile (captures the entire forward as a graph)
    → the Neuron Graph Compiler compiles the graph
      → NKI kernel part: wrap_nki() → the NKI Compiler compiles it separately
      → the rest: the Graph Compiler optimizes automatically
    → result: both compilers' outputs coexist in a single NEFF binary
```

### Comparison of NKI kernel registration methods

| | PyTorch Native (research/learning) | vLLM Plugin (serving/production) |
|---|---|---|
| **Kernel definition** | `@nki.jit` | `@nki.jit` (same) |
| **PyTorch integration** | `@nki_op` + `wrap_nki` → register a custom op | `wrap_nki()` → Plugin HOP dispatch |
| **Compilation unit** | per op or torch.compile graph | the entire forward as a single NEFF |
| **Required environment** | PyTorch Native Beta (torch-neuronx) | vLLM Neuron Plugin (no Beta needed) |

### Code example

```python
# 1. Define the NKI kernel
@nki.jit
def my_custom_attention(q_ref, k_ref, v_ref, ...):
    q = nl.load(q_ref[...])
    # ... SBUF operations ...
    nl.store(out_ref[...], result)

# 2. Register in the vLLM Plugin
from vllm_neuron.utils.nki_utils import wrap_nki
wrapped_attn = wrap_nki(my_custom_attention)

# 3. Call from model.py
def forward_prefill(self, q, k, v, ...):
    return wrapped_attn[grid](q, k, v, ...)
```



## References

- [Official docs: How to onboard a model to vLLM Neuron](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/vllm-neuron/docs/model-dev/onboarding-models.html)
- [Official docs: Debugging accuracy issues](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/vllm-neuron/docs/model-dev/accuracy-debugging-guide.html)
- [GitHub: vllm-neuron](https://github.com/vllm-project/vllm-neuron)
- [Reference implementation: Gemma4-31B on Trainium2](https://github.com/arminagha1234/Armin-Neuron/tree/main/gemma4-31b/vllm-neuron-Public_Final)
