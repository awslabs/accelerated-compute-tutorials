# NDD Day 2 Lab — PyTorch Native & NKI Kernel Optimization

## Lab Objectives

| # | Objective | Completion Criteria |
|---|------|----------|
| 1 | Move tensors to the Neuron device and run operations in PyTorch Native | `to('neuron')` + verify operation result |
| 2 | Run a training loop in Eager mode (identical to GPU code) | Confirm loss decreases |
| 3 | Generate a NEFF and compare performance with `torch.compile(backend="neuron")` | Confirm speedup over Eager |
| 4 | Replace the model's core operations with NKI Library kernels and measure performance | base → core 1.2x speedup |
| 5 | Use profiling to identify CPU fallback and bottleneck regions | List of fallback ops + profiling results |

> Total time: ~75 min (Lab 1: 35 min + Lab 2: 40 min)

## Lab Environment

| Item | Value |
| --- | --- |
| Instance | trn2.3xlarge (Trainium2 x 1 chip, 4 logical NeuronCores, HBM 96GB) |
| AMI | Deep Learning AMI Neuron (Ubuntu 24.04) — Neuron SDK 2.31 |
| PyTorch Native | neuronx-cc 2.26, nki 0.5.0, torch 2.11.0, torch-neuronx 2.11.3 |
| Virtual environment | `~/native_workshop_venv/` |
| Lab 1 code | `~/workspace/lab1/` |
| Lab 2 code | `~/workspace/lab2/` |

!!! info "What is PyTorch Native?"
    PyTorch Native is Neuron's next-generation PyTorch integration method. Rather than being XLA-based like before, it uses PyTorch's **PrivateUse1** device extension mechanism to access the device directly via `to('neuron')`. It works with the same pattern you would use for `to('cuda')` on a GPU.

## **Lab 0: Environment Check (5 min)**

### 0-1. Verify Trainium2 Hardware

```bash
neuron-ls

```

**Expected output:**

```
instance-type: trn2.3xlarge
+--------+--------+----------+--------+--------------+----------+------+
| NEURON | NEURON | NEURON   | NEURON | PCI          | CPU      | NUMA |
| DEVICE | CORES  | CORE IDS | MEMORY | BDF          | AFFINITY | NODE |
+--------+--------+----------+--------+--------------+----------+------+
| 0      | 4      | 0-3      | 96 GB  | 0000:33:00.0 | 0-11     | 0    |
+--------+--------+----------+--------+--------------+----------+------+

```

> Confirm 4 logical NeuronCores (LNC2 mode: physical 8 → logical 4) and 96 GB of HBM.

### 0-2. Activate the Python Virtual Environment

```bash
source ~/native_workshop_venv/bin/activate

```

Success is indicated when the prompt changes to `(native_workshop_venv)`.

!!! warning "You must activate this venv in every terminal."
    Be sure to run this each time you open a new terminal. It is **completely separate** from the vLLM venv used in Day 1. Both Lab 1 and Lab 2 use this same venv.

### 0-3. Verify the Neuron SDK Installation

```bash
pip list | grep -e neuron -e torch -e nki

```

**Expected output:**

```
neuronx-cc       2.26.6360.0+6f180f47
nki              0.5.0+28631259367.ga768afa6
torch            2.11.0
torch-neuronx    2.11.3.0.1417+1431f083.dev

```

Key packages:

- `torch` — standard PyTorch (upstream)
- `torch-neuronx` — Neuron device backend plugin (PrivateUse1)
- `neuronx-cc` — Neuron compiler (FX Graph → NEFF)
- `nki` — Neuron Kernel Interface

### 0-4. Verify the PyTorch Import

```bash
python -c "import torch; print(torch.__version__); t = torch.randn(2,2).to('neuron'); print(t)"

```

!!! note "The OperatorEntry warning is normal"
    The first time you run `import torch`, the following warning is printed:

    ```
    [W] Warning only once for all operators, other operators may also be overridden. Overriding a previously registered kernel for the same operator and the same dispatch key operator: aten::gather.out(...) dispatch key: PrivateUse1
    ```

    This is the normal process of the Neuron backend **registering ~2000 ATen ops under the PrivateUse1 key**.
    It overrides the existing default CPU kernels with Neuron kernels, and when this warning appears the backend has loaded correctly.
    It is printed only once and does not appear again afterward.

**Expected output**
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

## **Lab 1: Getting Started with PyTorch Native (35 min)**

!!! abstract "Learning Objectives"
    Experience firsthand the core patterns for using the Neuron device in PyTorch Native: (1) basic tensor operations, (2) Eager training, (3) torch.compile optimization, (4) NKI kernel integration.

### **Step 1: Device & Tensor Basics (~5 min)**

**Goal:** Learn how to place tensors on the Neuron device and run operations in PyTorch.

Open the Python interpreter and follow along line by line:

```bash
cd ~/workspace/lab1
python

```

```python
>>> import torch

# Create a CPU tensor
>>> cpu_tensor = torch.randn(3, 3)
>>> print(cpu_tensor.device)
cpu

# Move to the Neuron device
>>> neuron_tensor = cpu_tensor.to('neuron')
>>> print(neuron_tensor.device)
neuron:0

# Operate directly on Neuron (no need to go back to CPU)
>>> result = neuron_tensor * 2 + 1
>>> print(result)
tensor([[...]], device='neuron:0')

```

!!! note "Do you see the `NKI_ENABLE_TRACE_CACHE` warning?"
    `UserWarning: NKI_ENABLE_TRACE_CACHE=1: the NKI kernel compile cache is persisted across processes...`

    This is **normal**. It is a notice that the NKI kernel compilation results will be cached to disk so they load quickly from the second run onward. It has no effect on execution, so **ignore it**.

```python
# (continued)

# Device-agnostic code — works on both GPU and Neuron
>>> device = torch.accelerator.current_accelerator()
>>> print(device)
neuron:0

>>> portable_tensor = torch.randn(3, 3, device=device)
>>> print(portable_tensor.device)
neuron:0

>>> exit()

```

**Key points:**

| GPU | Neuron |
| --- | --- |
| `tensor.to('cuda')` | `tensor.to('neuron')` |
| `torch.device('cuda')` | `torch.device('neuron')` |
| `torch.cuda.synchronize()` | `torch.neuron.synchronize()` |

- Using `torch.accelerator.current_accelerator()` lets you write code that is portable across GPU and Neuron.

### **Step 2: Eager Mode Training (~10 min)**

**Goal:** Confirm that a standard PyTorch training loop runs **as-is** on Neuron.

```bash
python eager_mode.py

```

**Expected output:**

```
Using: neuron
Epoch 1, Loss: 0.7981
Epoch 2, Loss: 0.7964
...
Epoch 10, Loss: 0.7835

```

!!! success "Checkpoint"
    Success is indicated when the loss steadily decreases every epoch. Confirm that the structure is **100% identical** to GPU training code — the only thing changed is the single line `device = torch.device('neuron')`.

**Code highlights (eager_mode.py):**

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

!!! tip "Using int32"
    Neuron does not support int64. Create label tensors with `dtype=torch.int32`.

### **Step 3: torch.compile with Neuron Backend (~15 min)**

**Goal:** Compile the model with torch.compile(backend="neuron") and confirm that a NEFF is generated and runs correctly. The first run incurs compilation time, which is then cached.

```bash
python torch_compile.py

```

**Expected output:**

```
Input shape:  torch.Size([2, 10])
Output shape: torch.Size([2, 5])

```

!!! info "How torch.compile works"
    When you call `torch.compile(backend="neuron")`, internally:

```
1. TorchDynamo — captures Python bytecode and extracts an FX Graph
2. AOT Autograd — separates the forward/backward graphs
3. Neuron Backend — converts FX → Neuron IR
4. neuronx-cc — HW optimization → generates NEFF (execution binary)

The entire forward is fused into a single NEFF, eliminating per-op dispatch overhead.

```

### **Step 3 Additional: Understanding Asynchronous Execution and synchronize()**

Neuron uses an **asynchronous execution** model. The CPU "fires off" an operation and immediately moves on to the next line. For accurate benchmarks, you must wait for completion with `torch.neuron.synchronize()`.

```python
torch.neuron.synchronize()          # fence
start = time.perf_counter()
for _ in range(100):
    output = model(x)
torch.neuron.synchronize()          # wait for completion
elapsed = time.perf_counter() - start

```

!!! warning "What happens if you measure without synchronize()?"
    You only measure the CPU dispatch time — this measures only the time to send the command, not the actual compute time on the NeuronCore, so it is meaningless.

### **Step 4: NKI Kernel Integration (~5 min)**

**Goal:** Learn the basics of integrating an NKI kernel into PyTorch with the `@nki_op` pattern.

```bash
python nki_integration.py

```

**Expected output:**

```
Eager mode - NKI add result shape: torch.Size([128]), device: neuron:0
Compiled mode - NKI add result shape: torch.Size([128]), device: neuron:0

```

!!! success "Checkpoint"
    Success is indicated when the NKI kernel is called correctly in both Eager mode and Compiled mode. This is the foundation of the `@nki_op` pattern that you will use in earnest in Lab 2.

### **Step5: Distributed Training (FSDP)**

**Goal:** Confirm that distributed training using 4 NeuronCores works with `torchrun`.

```bash
NEURON_RT_VIRTUAL_CORE_SIZE=2 \
NEURON_RT_NUM_CORES=4 \
torchrun \
    --nproc_per_node 4 \
    --rdzv_backend c10d \
    --rdzv_endpoint localhost:29500 \
    distributed_fsdp.py

```

**Expected output:**

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

!!! note "Ignore the EFA warning"
    `NET/OFI Failed to initialize rdma protocol` — this warning appears because trn2.3xlarge does not have EFA. Intra-node communication is handled by NeuronLink, so it **has no effect on normal operation**.

### **Additional: SFT Fine-tuning**

**Goal:** Confirm that you can fine-tune an actual LLM (Qwen3-1.7B) in PyTorch Native.

```bash
# LoRA Fine-tuning (fast, memory-efficient)
./run_lora_finetune_hf.sh

# Full Fine-tuning (updates all parameters)
./run_full_finetune_hf.sh

```

**Expected output**

* After the compilation time elapses (about 5 to 10 minutes), confirm that the loss decreases

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

The core value of PyTorch Native: **the HuggingFace + PEFT training code you used on GPU works as-is.**

## **Lab 2: Optimizing the Model with NKI (40 min)**

!!! abstract "Learning Objectives"
    Replace the model's core operations with NKI Library's optimized kernels and measure the performance gain firsthand. Achieve a 1.5x speedup with 10 lines of code changes.

### **Lab 2 Code Structure**

```
~/workspace/lab2/
├── run.py                    ← Execution entry point (model selection, compile, benchmark)
├── nki_ops.py                ← @nki_op registration code (wrap_nki + nki_op pattern)
├── profile_utils.py          ← Profiling utilities
├── llama_base/               ← Pure PyTorch Llama (baseline)
│   ├── llama.py              ← Full model (forward loop)
│   ├── self_attention.py     ← Attention implementation
│   └── transformer_block.py  ← Layer block (Attn + MLP)
├── llama_nki_core/           ← MLP+RoPE replaced with nkilib core kernels
│   ├── llama_nki.py
│   ├── self_attention.py
│   └── transformer_block.py
└── llama_nki_experimental/   ← nkilib mega-kernel (entire layer including Attention)
    ├── llama_nki.py
    ├── self_attention.py
    └── transformer_block.py
```

**Key structure:**

<table style="min-width: 75px;"><colgroup><col style="min-width: 25px;"><col style="min-width: 25px;"><col style="min-width: 25px;"></colgroup><tbody><tr><th colspan="1" rowspan="1"><p>Folder</p></th><th colspan="1" rowspan="1"><p>Role</p></th><th colspan="1" rowspan="1"><p>What changes</p></th></tr><tr><td colspan="1" rowspan="1"><p><code>llama_base/</code></p></td><td colspan="1" rowspan="1"><p>Pure PyTorch — <code>nn.Linear</code> + manual RoPE + manual Attention</p></td><td colspan="1" rowspan="1"><p>None (baseline)</p></td></tr><tr><td colspan="1" rowspan="1"><p><code>llama_nki_core/</code></p></td><td colspan="1" rowspan="1"><p>Same as base, but MLP/RoPE replaced with the nkilib kernels in <code>nki_ops.py</code></p></td><td colspan="1" rowspan="1"><p>Calls <code>nki_mlp()</code>, <code>nki_rope()</code> in <code>transformer_block.py</code></p></td></tr><tr><td colspan="1" rowspan="1"><p><code>llama_nki_experimental/</code></p></td><td colspan="1" rowspan="1"><p>Replaces everything up to and including Attention with a mega-kernel</p></td><td colspan="1" rowspan="1"><p><code>self_attention.py</code> is a completely different implementation</p></td></tr><tr><td colspan="1" rowspan="1"><p><code>nki_ops.py</code></p></td><td colspan="1" rowspan="1"><p>nkilib import → wrap_nki → @nki_op registration</p></td><td colspan="1" rowspan="1"><p>The same pattern learned in S2</p></td></tr></tbody></table>

**What** `run.py` **does:**

1.  Selects the model folder via the `--model base/core/experimental` argument
    
2.  Applies `torch.compile(backend="neuron")` if `--compile` is present
    
3.  Does greedy decoding (token generation) if `--greedy` is present
    
4.  Warmup 3 times → Timing 50 tokens → prints throughput
    

**The relationship among the 3 folders:**

```
llama_base/             → all ops are PyTorch defaults (5 HBM round-trips)
llama_nki_core/         → MLP, RoPE replaced with nkilib kernels (3 HBM round-trips)
llama_nki_experimental/ → the entire layer in 1 mega-kernel (1 HBM round-trip)
```

**In other words, the only thing you change is the** `--model` **argument, and inside the code the same weights receive the same input while only the forward() path differs.** **If you open** `nki_ops.py`**, you'll see the** `@nki_op` **+** `wrap_nki` **pattern learned in S2 used exactly as-is.**

!!! info "LLM layer components — why replace these?"
    A single Transformer layer looks like this:

    ```
    input → [RMSNorm] → [QKV Linear] → [RoPE] → [Attention] → [Output Linear] → [RMSNorm] → [MLP(SwiGLU)] → output
    ```

    | Component | What it does (one line) |
    |----------|---------------|
    | **RMSNorm** | Normalizes tensor magnitude (stabilizes training) |
    | **QKV Linear** | Transforms the input into Query, Key, Value |
    | **RoPE** | Encodes token position information as a rotation |
    | **Attention** | "Where to look" — computes similarity via Q×K, then extracts information from V |
    | **MLP (SwiGLU)** | "Transform the information" — filters with a gate for a nonlinear transform (3 Linears + SiLU) |

    **Problem**: in the default PyTorch code, between each component the result is stored to HBM and re-read by the next.

    ```
    base:          [RMSNorm]↕HBM → [QKV]↕HBM → [RoPE]↕HBM → [Attn]↕HBM → [MLP] = 5 round-trips
    core:          [RMSNorm+QKV]↕HBM → [RoPE+Attn]↕HBM → [MLP(nki)]             = 3 round-trips
    experimental:  [everything processed inside SBUF]                            = 1 round-trip
    ```

    What the NKI kernel does = **reduce these HBM round-trips**. The same problem exists on GPU, which is why Flash Attention and CUDA Fused Kernels exist. On Neuron, SBUF (28MB) is much larger than GPU Shared Memory (a few hundred KB), so a wider range of fusion is possible.

### **Step 1: Running the Baseline (~5 min)**

**Goal:** Confirm the baseline performance of a Llama model written in pure PyTorch.

```bash
cd ~/workspace/lab2
python run.py --model base --compile --greedy

```

**Expected output:**

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

!!! success "Checkpoint"
    Confirm a throughput of around **359 tok/s**. This is the baseline without NKI.

### **Step 2: Code Analysis — "What exactly changed?" (~10 min)**

**Goal:** Analyze the code difference between base and core, and understand what the NKI kernel replacement is.

```bash
diff llama_base/transformer_block.py llama_nki_core/transformer_block.py

```

**Key Diff — MLP (FeedForward):**

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

!!! info "Why is it faster?"
    In pure PyTorch, gate, up, and down each run as separate operations. An HBM round-trip occurs every time.

```
The NKI fused kernel processes the 3 operations at once inside SBUF.
Since intermediate results are not written to HBM, it saves memory bandwidth.

```

**Checking nki_ops.py (NKI registration pattern):**

```bash
cat nki_ops.py | head -30

```

Key pattern: `wrap_nki()` + `@nki_op` → registers as a PyTorch custom op

### **Step 3: Running Core (~5 min)**

```bash
python run.py --model core --compile --greedy

```

**Expected output:**

```
Model   : core — NKI core (CTE prefill + TKG decode, static KV cache)
Throughput      : 435.3 tok/s

```

!!! success "Checkpoint"
    About **435 tok/s** — a **1.2x improvement** over base. This is the result achieved with ~10 lines of code changes.

### **Step 4: Experimental — Mega-kernel (~5 min)**

```bash
python run.py --model experimental --compile --greedy

```

**Expected output:**

```
Model   : experimental — NKI experimental (CTE prefill + megakernel decode, static KV cache)
Throughput      : 537.4 tok/s

```

!!! success "Checkpoint"
    About **537 tok/s** — a **1.5x improvement** over base. Experimental fuses the entire Transformer block into a single mega-kernel.

### **Step 5: Performance Comparison Summary**

| Variant | Throughput | vs. base | Change |
| --- | --- | --- | --- |
| base | 359 tok/s | 1.0x | Pure PyTorch (Graph Compiler only) |
| core | 435 tok/s | 1.2x | MLP + Attention NKI kernel replacement |
| experimental | 537 tok/s | 1.5x | Mega-kernel (entire block fused) |

### **Step 6: Profiling — Checking CPU Fallback**

**Goal:** Identify which ops in the model run on the NeuronCore and which fall back to the CPU.

#### Add fallback-check code to `run.py`

Add just **one line** right after the `Generated IDs` output in `run.py`:

```python
    print(f"\nCPU fallback ops: {torch_neuronx.get_fallback_ops()}")
```

> `torch_neuronx` is already imported, so no additional import is needed. The indentation is the same as the print statement above (4 spaces).

#### Run in Greedy mode

```bash
python run.py --model base --compile --greedy
```

**Expected output (last line):**

```bash
CPU fallback ops: ['aten::argmax.out']
```

→ `argmax` is also a CPU fallback, but with a single call its throughput impact is negligible (426 tok/s).

#### Run in Sampling mode (fallback with large performance impact)

```bash
python run.py --model base --compile
```

**Expected output (last line):**

```bash
CPU fallback ops: ['aten::sort.values_stable', 'aten::multinomial']
```

→ When `sort` and `multinomial`, needed for top-p filtering, fall back to CPU, an HBM↔CPU round-trip occurs **for every token** → 52 tok/s (8x slower!).

!!! info "Why does this difference occur?"
    | Mode | Fallback ops | Throughput | Impact |
    |------|-------------|-----------|------|
    | `--greedy` | `argmax.out` (1) | 426 tok/s | Negligible (once per token) |
    | sampling | `sort` + `multinomial` (2) | 52 tok/s | **Severe** (repeated every token) |

    The same model, the same compile, yet an **8x performance difference arises from the difference in CPU fallback ops**.

    In practice, vLLM handles sampling itself, so this fallback is not a problem.
    Here, the goal is to learn **how to detect fallbacks**.

!!! tip "Key API"
    ```python
    torch_neuronx.get_fallback_ops()
    ```
    Returns the cumulative list of ops that fell back to the CPU in the current process. You can call it after execution without modifying model code.

### **Step 7: Summary of the Code Diff Pattern**

Every NKI kernel replacement follows the same pattern:

| Step | File | Task |
| --- | --- | --- |
| 1 | `nki_ops.py` | Register the kernel with `wrap_nki()` + `@nki_op` |
| 2 | `transformer_block.py` | Replace the MLP forward() |
| 3 | `self_attention.py` | Replace the Attention forward() |
| 4 | Run | `python run.py --model core --compile --greedy` |
| 5 | Verify | Compare throughput |

**Lab checklist:**

1. Check the kernels to use in `nki_ops.py` (nki_mlp, nki_rmsnorm, nki_attn, etc.)
2. Check weight shapes — pass `.weight` directly (nkilib handles the transpose internally)
3. Replace the existing forward() calls with nki function calls
4. Run → verify accuracy → compare benchmark

## Wrap-up

!!! quote "What you learned today"
    - **Lab 1** : In PyTorch Native, a single line of `.to('neuron')` makes GPU code run on Neuron
    - **Lab 2** : 10 lines of nkilib kernel replacement for a 1.5x speedup — you don't have to write kernels yourself
    - **Key message** : NKI starts not with "writing from scratch" but with "picking up and using proven kernels"

## Reference Links

- [PyTorch Native Overview](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/frameworks/torch/pytorch-native-overview.html)
- [NKI Documentation](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/nki/index.html)
- [NKI Library](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/nki/library/about/index.html)
- [torch.accelerator API](https://docs.pytorch.org/docs/main/accelerator.html)
