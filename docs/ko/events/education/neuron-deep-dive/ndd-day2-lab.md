# NDD Day 2 Lab — PyTorch Native & NKI 커널 최적화

## 실습 목표

| # | 목표 | 완료 기준 |
|---|------|----------|
| 1 | PyTorch Native에서 Neuron 디바이스로 텐서 이동 및 연산 수행 | `to('neuron')` + 연산 결과 확인 |
| 2 | Eager 모드로 학습 루프 실행 (GPU 코드와 동일) | Loss 감소 확인 |
| 3 | `torch.compile(backend="neuron")`으로 NEFF 생성 및 성능 비교 | Eager 대비 속도 향상 확인 |
| 4 | NKI Library 커널로 모델 핵심 연산 교체 후 성능 측정 | base → core 1.2x 성능 향상 |
| 5 | 프로파일링으로 CPU fallback 및 병목 구간 확인 | fallback ops 목록 + 프로파일 결과 |

> 총 소요: ~75분 (Lab 1: 35분 + Lab 2: 40분)

---

## 실습 환경

| 항목 | 값 |
| --- | --- |
| 인스턴스 | trn2.3xlarge (Trainium2 x 1 chip, 4 logical NeuronCores, HBM 96GB) |
| AMI | Deep Learning AMI Neuron (Ubuntu 24.04) — Neuron SDK 2.31 |
| PyTorch Native | neuronx-cc 2.26, nki 0.5.0, torch 2.11.0, torch-neuronx 2.11.3 |
| 가상환경 | `~/native_workshop_venv/` |
| Lab 1 코드 | `~/workspace/lab1/` |
| Lab 2 코드 | `~/workspace/lab2/` |

!!! info "PyTorch Native란?"
    PyTorch Native는 Neuron의 차세대 PyTorch 통합 방식입니다. 기존 XLA 기반이 아닌, PyTorch의 **PrivateUse1** 디바이스 확장 메커니즘을 사용하여 `to('neuron')`으로 직접 디바이스에 접근합니다. GPU에서 `to('cuda')`를 쓰듯 동일한 패턴으로 동작합니다.

---

## **Lab 0: 환경 확인 (5분)**

### 0-1. Trainium2 하드웨어 확인

```bash
neuron-ls

```

**예상 출력:**

```
instance-type: trn2.3xlarge
+--------+--------+----------+--------+--------------+----------+------+
| NEURON | NEURON | NEURON   | NEURON | PCI          | CPU      | NUMA |
| DEVICE | CORES  | CORE IDS | MEMORY | BDF          | AFFINITY | NODE |
+--------+--------+----------+--------+--------------+----------+------+
| 0      | 4      | 0-3      | 96 GB  | 0000:33:00.0 | 0-11     | 0    |
+--------+--------+----------+--------+--------------+----------+------+

```

> 4 logical NeuronCores (LNC2 모드: 물리 8 → 논리 4)와 96 GB HBM을 확인합니다.

### 0-2. Python 가상환경 활성화

```bash
source ~/native_workshop_venv/bin/activate

```

프롬프트가 `(native_workshop_venv)`로 바뀌면 성공입니다.

!!! warning "모든 터미널에서 이 venv를 활성화해야 합니다."
    새 터미널을 열 때마다 반드시 실행하세요. Day 1에서 사용한 vLLM venv와는 **완전히 별개** 입니다. Lab 1과 Lab 2 모두 동일한 이 venv를 사용합니다.

### 0-3. Neuron SDK 설치 확인

```bash
pip list | grep -e neuron -e torch -e nki

```

**예상 출력:**

```
neuronx-cc       2.26.6360.0+6f180f47
nki              0.5.0+28631259367.ga768afa6
torch            2.11.0
torch-neuronx    2.11.3.0.1417+1431f083.dev

```

핵심 패키지:

- `torch` — 표준 PyTorch (upstream)
- `torch-neuronx` — Neuron 디바이스 백엔드 플러그인 (PrivateUse1)
- `neuronx-cc` — Neuron 컴파일러 (FX Graph → NEFF)
- `nki` — Neuron Kernel Interface

### 0-4. PyTorch import 확인

```bash
python -c "import torch; print(torch.__version__); t = torch.randn(2,2).to('neuron'); print(t)"

```

!!! note "OperatorEntry 경고는 정상입니다"
    처음 `import torch`를 실행하면 다음과 같은 경고가 출력됩니다:
    
    ```
    [W] Warning only once for all operators, other operators may also be overridden. Overriding a previously registered kernel for the same operator and the same dispatch key operator: aten::gather.out(...) dispatch key: PrivateUse1
    ```

    이는 Neuron 백엔드가 **~2000개 ATen op을 PrivateUse1 키로 등록**하는 정상 과정입니다.
    기존 CPU 기본 커널을 Neuron 커널로 덮어씌우는 것이며, 이 경고가 뜨면 백엔드가 정상 로드된 것입니다.
    한 번만 출력되고 이후에는 나타나지 않습니다.




**예상 출력** 
```
$ python -c "import torch; print(torch.__version__); t = torch.randn(2,2).to('neuron'); print(t)"
[W818 08:33:06.095561353 OperatorEntry.cpp:208] Warning: Warning only once for all operators,  other operators may also be overridden.
  Overriding a previously registered kernel for the same operator and the same dispatch key
  operator: aten::gather.out(Tensor self, int dim, Tensor index, *, bool sparse_grad=False, Tensor(a!) out) -> Tensor(a!)
    registered at /pytorch/build/aten/src/ATen/RegisterSchema.cpp:6
  dispatch key: PrivateUse1
  previous kernel: registered at /pytorch/build/aten/src/ATen/RegisterCPU_3.cpp:7637
       new kernel: registered at NeuronDispatcher.cpp:0 (function operator())
2.11.0+cu130
tensor([[-0.4285,  1.3709],
        [ 0.1188,  0.0435]], device='neuron:0')

```


---

## **Lab 1: PyTorch Native 시작하기 (35분)**

!!! abstract "학습 목표"
    PyTorch Native에서 Neuron 디바이스를 사용하는 핵심 패턴을 직접 체험합니다: (1) 텐서 기본 연산, (2) Eager 학습, (3) torch.compile 최적화, (4) NKI 커널 통합.



### **Step 1: Device & Tensor Basics (~5분)**

**목표:** PyTorch에서 Neuron 디바이스에 텐서를 올리고 연산하는 방법을 확인합니다.

Python 인터프리터를 열고 라인별로 따라해보세요:

```bash
cd ~/workspace/lab1
python

```

```python
>>> import torch

# CPU 텐서 생성
>>> cpu_tensor = torch.randn(3, 3)
>>> print(cpu_tensor.device)
cpu

# Neuron 디바이스로 이동
>>> neuron_tensor = cpu_tensor.to('neuron')
>>> print(neuron_tensor.device)
neuron:0

# Neuron에서 직접 연산 (CPU로 돌아갈 필요 없음)
>>> result = neuron_tensor * 2 + 1
>>> print(result)
tensor([[...]], device='neuron:0')

```

!!! note "`NKI_ENABLE_TRACE_CACHE` 워닝이 보이나요?"
    `UserWarning: NKI_ENABLE_TRACE_CACHE=1: the NKI kernel compile cache is persisted across processes...`

    
    이것은 **정상** 입니다. NKI 커널 컴파일 결과를 디스크에 캐시하여 두 번째 실행부터
    빠르게 로드하겠다는 알림입니다. 실행에 영향 없으므로 **무시하세요** .

    

```python
# (계속)

# 디바이스 무관(Device-agnostic) 코드 — GPU/Neuron 양쪽에서 동작
>>> device = torch.accelerator.current_accelerator()
>>> print(device)
neuron:0

>>> portable_tensor = torch.randn(3, 3, device=device)
>>> print(portable_tensor.device)
neuron:0

>>> exit()

```

**핵심 포인트:**

| GPU | Neuron |
| --- | --- |
| `tensor.to('cuda')` | `tensor.to('neuron')` |
| `torch.device('cuda')` | `torch.device('neuron')` |
| `torch.cuda.synchronize()` | `torch.neuron.synchronize()` |

- `torch.accelerator.current_accelerator()`를 사용하면 GPU/Neuron 이식 가능한 코드를 작성할 수 있습니다.

---

### **Step 2: Eager Mode Training (~10분)**

**목표** : 표준 PyTorch 학습 루프가 Neuron에서 **그대로** 동작하는 것을 확인합니다.

```bash
python eager_mode.py

```

**예상 출력:**

```
Using: neuron
Epoch 1, Loss: 0.7981
Epoch 2, Loss: 0.7964
...
Epoch 10, Loss: 0.7835

```

!!! success "체크포인트"
    Loss가 Epoch마다 꾸준히 감소하면 성공입니다. GPU 학습 코드와 **100% 동일한 구조** 임을 확인하세요 — 바꾼 것은 `device = torch.device('neuron')` 한 줄뿐입니다.

**코드 핵심 (eager_mode.py):**

```python
device = torch.device('neuron')
model = nn.Sequential(nn.Linear(10, 2)).to(device)
X = torch.randn(100, 10).to(device)
y = torch.randint(0, 2, (100,), dtype=torch.int32).to(device)

for epoch in range(10):
    output = model(X)
    loss = criterion(output, y)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

```

!!! tip "int32 사용"
    Neuron은 int64를 지원하지 않습니다. Label tensor는 `dtype=torch.int32`로 생성하세요.

---

### **Step 3: torch.compile with Neuron Backend (~15분)**

**목표**: `torch.compile(backend="neuron")`으로 모델을 컴파일하면, Neuron 컴파일러가 전체 그래프를 최적화하여 성능이 크게 향상되는 것을 확인합니다.

```bash
python torch_compile.py

```

**예상 출력:**

```
Input shape:  torch.Size([2, 10])
Output shape: torch.Size([2, 5])

```

!!! info "torch.compile의 원리"
    `torch.compile(backend="neuron")`을 호출하면 내부적으로:

```
1. TorchDynamo — Python bytecode를 캡처해 FX Graph 추출
2. AOT Autograd — Forward/Backward 그래프 분리
3. Neuron Backend — FX → Neuron IR 변환
4. neuronx-cc — HW 최적화 → NEFF (실행 바이너리) 생성

전체 forward가 하나의 NEFF로 융합되어 op별 dispatch overhead가 제거됩니다.

```

---

### **Step 3 Additional: 비동기 실행과 synchronize() 이해**

Neuron은 **비동기 실행** 모델입니다. CPU는 연산을 "발사"하고 즉시 다음 줄로 넘어갑니다. 정확한 벤치마크를 위해서는 반드시 `torch.neuron.synchronize()`로 완료를 대기해야 합니다.

```python
torch.neuron.synchronize()          # fence
start = time.perf_counter()
for _ in range(100):
    output = model(x)
torch.neuron.synchronize()          # 완료 대기
elapsed = time.perf_counter() - start

```

!!! warning "synchronize() 없이 측정하면?"
    CPU dispatch 시간만 측정됩니다 — NeuronCore의 실제 연산 시간이 아닌, 명령을 보내는 시간만 재는 것이므로 무의미합니다.

---

### **Step 4: NKI 커널 통합 (~5분)**

**목표** : `@nki_op` 패턴으로 NKI 커널을 PyTorch에 통합하는 기초를 확인합니다.

```bash
python nki_integration.py

```

**예상 출력:**

```
Eager mode - NKI add result shape: torch.Size([128]), device: neuron:0
Compiled mode - NKI add result shape: torch.Size([128]), device: neuron:0

```

!!! success "체크포인트"
    Eager 모드와 Compiled 모드 모두에서 NKI 커널이 정상 호출되면 성공입니다. 이것이 Lab 2에서 본격적으로 사용할 `@nki_op` 패턴의 기초입니다.

---

### **Step5: 분산 학습 (FSDP)**

**목표**: `torchrun`으로 4 NeuronCore를 활용한 분산 학습이 동작함을 확인합니다.

```bash
NEURON_RT_VIRTUAL_CORE_SIZE=2 \
NEURON_RT_NUM_CORES=4 \
torchrun \
    --nproc_per_node 4 \
    --rdzv_backend c10d \
    --rdzv_endpoint localhost:29500 \
    distributed_fsdp.py

```

**예상 출력:**

```
[Rank 0/4] Initialized on neuron:0
[Rank 1/4] Initialized on neuron:1
[Rank 2/4] Initialized on neuron:2
[Rank 3/4] Initialized on neuron:3
Iteration 1/5, Loss: 1.0071
...
Iteration 5/5, Loss: 0.9876
Training complete!

```

!!! note "EFA 경고는 무시하세요"
    `NET/OFI Failed to initialize rdma protocol` — trn2.3xlarge에는 EFA가 없어서 나오는 경고입니다. 노드 내 통신은 NeuronLink로 처리되므로 **정상 동작에 영향 없습니다**.

---

### **Additional: SFT Fine-tuning**

**목표**: 실제 LLM (Qwen3-1.7B)을 PyTorch Native에서 fine-tuning할 수 있음을 확인합니다.

```bash
# LoRA Fine-tuning (빠름, 메모리 효율적)
./run_lora_finetune_hf.sh

# Full Fine-tuning (전체 파라미터 업데이트)
./run_full_finetune_hf.sh

```

**예상 출력**

* 컴파일 시간 경과 후(약 5분~10분) Loss 가 감소하는 것을 확인하세요

* LoRA Fine-tuning
```bash
WARNING:torch_neuronx.python_ops.dtype_autocast:Neuron backend does not support int64. Automatically casting to int32. Consider using int32 directly for better performance until native int64 support is added.
WARNING:torch_neuronx.python_ops.dtype_autocast:Neuron backend does not support int64. Automatically casting to int32. Consider using int32 directly for better performance until native int64 support is added.
step=10/92 loss=17.0549 tok/s=6446 ms/step=5083.7
step=20/92 loss=12.6415 tok/s=6519 ms/step=5026.2
step=30/92 loss=7.7104 tok/s=6549 ms/step=5003.2
step=40/92 loss=5.3484 tok/s=6447 ms/step=5082.5
step=50/92 loss=4.4552 tok/s=6630 ms/step=4942.2
step=60/92 loss=3.6861 tok/s=6659 ms/step=4920.9
step=70/92 loss=2.9134 tok/s=6652 ms/step=4926.1
step=80/92 loss=2.5239 tok/s=6672 ms/step=4911.5
step=90/92 loss=2.2648 tok/s=6634 ms/step=4939.4
Saving final model shards to Qwen3-1.7B-LoRA-Python-Coder/shard-{0..3}
Training complete
==========================================
Training completed. LoRA adapter saved to: Qwen3-1.7B-LoRA-Python-Coder
==========================================

```

* Full Fine-tuning 
```bash
directly for better performance until native int64 support is added.
WARNING:torch_neuronx.python_ops.dtype_autocast:Neuron backend does not support int64. Automatically casting to int32. Consider using int32 directly for better performance until native int64 support is added.
WARNING:torch_neuronx.python_ops.dtype_autocast:Neuron backend does not support int64. Automatically casting to int32. Consider using int32 directly for better performance until native int64 support is added.
step=10/92 loss=19.9439 tok/s=743.4 ms/step=44077.9
step=20/92 loss=19.6373 tok/s=6852.1 ms/step=4782.2
step=30/92 loss=19.4491 tok/s=6821.1 ms/step=4803.9
step=40/92 loss=19.0041 tok/s=6884.8 ms/step=4759.5
step=50/92 loss=17.8819 tok/s=6894.3 ms/step=4752.9
step=60/92 loss=16.6132 tok/s=6878.2 ms/step=4764.0
step=70/92 loss=15.4918 tok/s=6888.2 ms/step=4757.1
step=80/92 loss=14.4292 tok/s=6844.9 ms/step=4787.2
step=90/92 loss=12.9341 tok/s=6881.7 ms/step=4761.6
Saving final model to Qwen3-1.7B-Full-Finetuned-HF
Writing model shards: 100%|██████████████████████████████████████████████████████████████████████████████████| 1/1 [00:06<00:00,  6.15s/it]
Training completed
==========================================
Training completed. Model saved to: Qwen3-1.7B-Full-Finetuned-HF
==========================================

```



PyTorch Native의 핵심 가치: **GPU에서 쓰던 HuggingFace + PEFT 학습 코드가 그대로 동작합니다.**



## **Lab 2: NKI로 모델 최적화 하기 (40분)**

!!! abstract "학습 목표"
    NKI Library의 최적화된 커널로 모델의 핵심 연산을 교체하고, 성능 향상을 직접 측정합니다. 코드 10줄 변경으로 1.5x 성능 향상을 달성합니다.



### **Lab 2 코드 구조**

```
~/workspace/lab2/
├── run.py                    ← 실행 진입점 (모델 선택, 컴파일, 벤치마크)
├── nki_ops.py                ← @nki_op 등록 코드 (wrap_nki + nki_op 패턴)
├── profile_utils.py          ← 프로파일링 유틸리티
├── llama_base/               ← 순수 PyTorch Llama (기준선)
│   ├── llama.py              ← 모델 전체 (forward loop)
│   ├── self_attention.py     ← Attention 구현
│   └── transformer_block.py  ← 레이어 블록 (Attn + MLP)
├── llama_nki_core/           ← nkilib core 커널로 MLP+RoPE 교체
│   ├── llama_nki.py
│   ├── self_attention.py
│   └── transformer_block.py
└── llama_nki_experimental/   ← nkilib mega-kernel (Attention 포함 전체)
    ├── llama_nki.py
    ├── self_attention.py
    └── transformer_block.py
```

**핵심 구조:**

<table style="min-width: 75px;"><colgroup><col style="min-width: 25px;"><col style="min-width: 25px;"><col style="min-width: 25px;"></colgroup><tbody><tr><th colspan="1" rowspan="1"><p>폴더</p></th><th colspan="1" rowspan="1"><p>역할</p></th><th colspan="1" rowspan="1"><p>바뀌는 것</p></th></tr><tr><td colspan="1" rowspan="1"><p><code>llama_base/</code></p></td><td colspan="1" rowspan="1"><p>순수 PyTorch — <code>nn.Linear</code> + 직접 RoPE + 직접 Attention</p></td><td colspan="1" rowspan="1"><p>없음 (기준선)</p></td></tr><tr><td colspan="1" rowspan="1"><p><code>llama_nki_core/</code></p></td><td colspan="1" rowspan="1"><p>base와 동일하되, MLP/RoPE를 <code>nki_ops.py</code>의 nkilib 커널로 교체</p></td><td colspan="1" rowspan="1"><p><code>transformer_block.py</code>에서 <code>nki_mlp()</code>, <code>nki_rope()</code> 호출</p></td></tr><tr><td colspan="1" rowspan="1"><p><code>llama_nki_experimental/</code></p></td><td colspan="1" rowspan="1"><p>Attention까지 통째로 mega-kernel로 교체</p></td><td colspan="1" rowspan="1"><p><code>self_attention.py</code>가 완전 다른 구현</p></td></tr><tr><td colspan="1" rowspan="1"><p><code>nki_ops.py</code></p></td><td colspan="1" rowspan="1"><p>nkilib import → wrap_nki → @nki_op 등록</p></td><td colspan="1" rowspan="1"><p>S2에서 배운 패턴 그대로</p></td></tr></tbody></table>

`run.py`**가 하는 일:**

1.  `--model base/core/experimental` 인자로 모델 폴더 선택
    
2.  `--compile` 있으면 `torch.compile(backend="neuron")` 적용
    
3.  `--greedy` 있으면 greedy decoding (token generation)
    
4.  Warmup 3회 → Timing 50 tokens → throughput 출력
    

**3개 폴더의 관계:**

```
llama_base/             → 모든 op이 PyTorch 기본 (HBM 왕복 5회)
llama_nki_core/         → MLP, RoPE를 nkilib 커널로 교체 (HBM 왕복 3회)
llama_nki_experimental/ → 레이어 전체를 1개 mega-kernel (HBM 왕복 1회)
```

**즉, 여러분이 바꾸는 건** `--model` **인자뿐이고, 코드 내부에서는 동일한 weight에 같은 입력을 넣되 forward() 경로만 달라집니다.** `nki_ops.py`**를 열어보면 S2에서 배운** `@nki_op` **+** `wrap_nki` **패턴이 그대로 사용됩니다.**

---

### **Step 1: Baseline 실행 (~5분)**

**목표**: 순수 PyTorch로 작성된 Llama 모델의 기준 성능을 확인합니다.

```bash
cd ~/workspace/lab2
python run.py --model base --compile --greedy

```

**예상 출력:**

```
Model   : base — Baseline (pure PyTorch ops, RoPE, static KV cache)
Size    : small
Compile : True
Tokens  : 50

Params  : 41,556,480  (79.3 MB bfloat16)

Warmup...
Timing...
Total time      : 0.139s
Tokens generated: 50
Throughput      : 359.0 tok/s

```

!!! success "체크포인트"
    약 **359 tok/s** 전후의 throughput을 확인하세요. 이것이 NKI 없는 기준선입니다.

---

### **Step 2: 코드 분석 — "뭘 바꿨길래?" (~10분)**

**목표**: base와 core의 코드 차이를 분석하고, NKI 커널 교체가 무엇인지 이해합니다.

```bash
diff llama_base/transformer_block.py llama_nki_core/transformer_block.py

```

**핵심 Diff — MLP (FeedForward):**

```python
def forward(self, x):
    gate = F.silu(self.gate_proj(x))
    up = self.up_proj(x)
    down = self.down_proj(gate * up)
    return down

```

```python
from nki_ops import nki_mlp

def forward(self, x):
    return nki_mlp(
        x,
        self.gate_proj.weight,
        self.up_proj.weight,
        self.down_proj.weight
    )

```

!!! info "왜 빨라지는가?"
    순수 PyTorch에서는 gate, up, down 각각이 별도 연산으로 실행됩니다. 매번 HBM 왕복이 발생합니다.

```
NKI fused 커널은 3개 연산을 SBUF 안에서 한 번에 처리합니다.
중간 결과가 HBM에 쓰여지지 않으므로 메모리 대역폭을 절약합니다.

```

**nki_ops.py 확인 (NKI 등록 패턴):**

```bash
cat nki_ops.py | head -30

```

핵심 패턴: `wrap_nki()` + `@nki_op` → PyTorch custom op으로 등록

---

### **Step 3: Core 실행 (~5분)**

```bash
python run.py --model core --compile --greedy

```

**예상 출력:**

```
Model   : core — NKI core (CTE prefill + TKG decode, static KV cache)
Throughput      : 435.3 tok/s

```

!!! success "체크포인트"
    약 **435 tok/s** — base 대비 **1.2x 향상**. 코드 ~10줄 변경으로 달성한 결과입니다.

---

### **Step 4: Experimental — Mega-kernel (~5분)**

```bash
python run.py --model experimental --compile --greedy

```

**예상 출력:**

```
Model   : experimental — NKI experimental (CTE prefill + megakernel decode, static KV cache)
Throughput      : 537.4 tok/s

```

!!! success "체크포인트"
    약 **537 tok/s** — base 대비 **1.5x 향상**. Experimental은 Transformer block 전체를 하나의 mega-kernel로 융합합니다.

---

### Step 5: 성능 비교 정리

| 변종 | Throughput | base 대비 | 변경 내용 |
| --- | --- | --- | --- |
| base | 359 tok/s | 1.0x | 순수 PyTorch (Graph Compiler만) |
| core | 435 tok/s | 1.2x | MLP + Attention NKI 커널 교체 |
| experimental | 537 tok/s | 1.5x | Mega-kernel (전체 block 융합) |

---

### **Step 6: 프로파일링 — CPU fallback 확인**

**목표**: 어떤 op이 NeuronCore에서 실행되고 어떤 op이 CPU로 빠지는지 확인합니다.

**테스트 파일 생성:**

```bash
# cpu_fallback_test.py
import torch
import torch_neuronx

x = torch.randn(4, 256, dtype=torch.bfloat16).to("neuron")

# 다양한 op 실행
_ = torch.unique(x)       # ← CPU fallback 발생
_ = torch.topk(x, k=5)   # ← Neuron 실행
_ = torch.mm(x.reshape(4, 256), torch.randn(256, 128, dtype=torch.bfloat16).to("neuron"))

# Fallback 확인
fallback_ops = torch_neuronx.get_fallback_ops()
print(f"CPU fallback ops ({len(fallback_ops)}):")
for op in fallback_ops:
    print(f"  - {op}")

```

!!! info 
    이 Lab의 llama\_base 코드에서는 CPU fallback이 발생하지 않습니다" llama\_base는 Neuron 지원 op만으로 작성되어 있어 모든 op이 NC에서 실행됩니다. 실무에서 HuggingFace 모델을 그대로 올릴 때는 일부 op이 CPU로 빠질 수 있습니다. 아래 예시로 fallback이 어떻게 감지되는지 체험해보세요.


**기대 출력:**

```bash
CPU fallback ops (1):
  - aten::_unique2
```

---

### **Step 7: Code Diff 패턴 정리**

모든 NKI 커널 교체는 동일한 패턴을 따릅니다:

| 단계 | 파일 | 작업 |
| --- | --- | --- |
| 1 | `nki_ops.py` | `wrap_nki()` + `@nki_op`으로 커널 등록 |
| 2 | `transformer_block.py` | MLP forward() 교체 |
| 3 | `self_attention.py` | Attention forward() 교체 |
| 4 | 실행 | `python run.py --model core --compile --greedy` |
| 5 | 검증 | throughput 비교 |

**실습 체크리스트:**

1. `nki_ops.py`에서 사용할 커널 확인 (nki_mlp, nki_rmsnorm, nki_attn 등)
2. weight shape 확인 — `.weight` 직접 전달 (nkilib이 내부에서 transpose 처리)
3. 기존 forward() 호출을 nki 함수 호출로 교체
4. 실행 → 정확도 검증 → 벤치마크 비교

---

## 마무리

!!! quote "오늘 배운 것"
    - **Lab 1**: PyTorch Native에서 `.to('neuron')` 한 줄로 GPU 코드가 Neuron에서 동작 
    - **Lab 2**: nkilib 커널 교체 10줄로 1.5x 성능 향상 — 커널을 직접 작성하지 않아도 됨 
    - **핵심 메시지**: NKI는 "처음부터 작성"이 아닌 "검증된 커널을 갖다 쓰는 것"부터 시작

---

## 참고 링크

- [PyTorch Native Overview](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/frameworks/torch/pytorch-native-overview.html)
- [NKI Documentation](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/nki/index.html)
- [NKI Library](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/nki/library/about/index.html)
- [torch.accelerator API](https://docs.pytorch.org/docs/main/accelerator.html)

