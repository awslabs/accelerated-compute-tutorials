!!! warning "Classic Guide"
    This document is a guide based on NxD Inference (Maintenance Mode).
    For new deployments, we recommend the [vLLM Neuron Plugin](../vllm/index.md).

# Serving Qwen3 8B Instruct on Trainium2 with vLLM + NxDI

This guide explains how to serve the [**Qwen3 8B Instruct**](https://huggingface.co/Qwen/Qwen3-8B) model on an **AWS Trainium2 `trn2.48xlarge`** instance using **vLLM 0.13 + NeuronX Distributed Inference (NxDI)**.

**Model Information:**
- **Model**: Qwen/Qwen3-8B
- **Parameters**: 8B
- **License**: Apache 2.0 (Open Model)
- **Context length**: Up to 32K

**⚠️ Important: Instance used**
- Qwen3 8B is roughly a 16 GB model, so it **can run on trn2.48xlarge (64 NeuronCores) or smaller instances**
- This guide is written for trn2.48xlarge

**🔄 How to run:**
This guide describes two ways to run it.
1.  **Quick Start (automatic compilation):** A way to start the server quickly for simple testing.
2.  **Recommended approach (two-stage process):** A way to apply all optimization options and operate reliably.



## ✅ Prerequisites

Before you begin, make sure of the following.

1. **Instance running:** The `trn2.48xlarge` or a smaller Trainium2 instance must be active (`Running`).
   * 👉 **[Guide: Launching an EC2 instance](https://github.com/leesjpe/compute-foundation-on-aws/blob/main/ec2/ec2-dlami-neuron.md)**

2. **Use a DLAMI:** The Hugging Face Neuron Deep Learning AMI or the AWS Deep Learning AMI (Neuron) is recommended.
   * Tested and written on Neuron SDK 2.27.1
   * Includes the vLLM 0.13 Neuron virtual environment

3. **Hugging Face authentication:**
   * Qwen3 is an open model, so no separate access permission is required
   * However, logging in is recommended to improve download speed

4. **(Optional) High-speed storage setup:**
   * To speed up model downloads, model compilation, and caching, you can consider using local NVMe SSD (RAID 0).
   * 👉 **[Guide: High-speed storage setup (NVMe RAID 0)](https://github.com/leesjpe/compute-foundation-on-aws/blob/main/storage/local-nvme-setup.md)**



## 1. 🚀 Environment Setup

### Step 1-1: Activate the virtual environment

The DLAMI includes a pre-configured vLLM 0.13 Neuron virtual environment.

```bash
# Activate the vLLM 0.13 Neuron inference environment
source /opt/aws_neuronx_venv_pytorch_inference_vllm_0_13/bin/activate
```

**Verify the environment:**
```bash
# Check the Python version
python --version

# Check installed packages
pip list | grep -E "neuronx|vllm|transformers"

# Check the vLLM version
vllm --version
```

**Test environment:**
- Python 3.12.3
- libneuronxla                      2.2.14584.0+06ac23d1
- neuronx-cc                        2.22.12471.0+b4a00d10
- neuronx-distributed               0.16.25997+f431c02e
- neuronx-distributed-inference     0.7.15063+bafa28d5
- torch-neuronx                     2.9.0.2.11.19912+e48cd891
- transformers                      4.56.2
- vllm                              0.13.0

### Step 1-2: Check the Neuron SDK version

```bash
# Check the Neuron SDK version
dpkg-query -W -f='${Version}\n' aws-neuronx-tools

# Check NeuronCores
neuron-ls
```

**Example trn2.48xlarge output:**
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

### Step 1-3: Download the model

Download the model ahead of time to the location you want.

```bash
# Create the model storage directory
mkdir -p ~/models
cd ~/models

# Download the Qwen3 8B Instruct model
huggingface-cli download Qwen/Qwen3-8B \
    --local-dir Qwen3-8B

# Verify the download
ls -lh Qwen3-8B/
```

**Expected download size:** ~16 GB

**Downloaded file structure:**
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

### 💡 Quick Start (automatic compilation)

For simple testing, you can let the vLLM server compile the model automatically.

```bash
# Set environment variables
export VLLM_NEURON_FRAMEWORK="neuronx-distributed-inference"

# Run the vLLM server (compiles automatically on first run, takes 10-30 minutes)
python -m vllm.entrypoints.openai.api_server \
    --model /home/ubuntu/models/Qwen3-8B \
    --tensor-parallel-size 64 \
    --max-num-seqs 1 \
    --max-model-len 6400 \
    --block-size 16 \
    --port 8000
```

**Pre-compilation is recommended in production environments:**
- Easier debugging if compilation fails
- Shorter server startup time (1-3 minutes)
- Compilation logs can be reviewed clearly
- AWS official recommendation

## 2. 🔧 Compile the model (once on first run)

To run Qwen3 8B on Trainium2, you must first compile the model. This runs only once on the first execution, and the compiled model is reused.

### Step 2-1: Create the compile script

Create a working directory and write the compile script.

```bash
# Create the working directory
mkdir -p ~/qwen3-8b-inference
cd ~/qwen3-8b-inference
```

**compile_model.sh:**
```bash
#!/bin/bash

# Set the model paths
MODEL_PATH="/home/ubuntu/models/Qwen3-8B"
COMPILED_MODEL_PATH="/home/ubuntu/compiled_models/Qwen3-8B"

# Create the directory for the compiled model
mkdir -p $COMPILED_MODEL_PATH

# Neuron runtime settings
NUM_CORES=128      # number of physical cores on trn2.48xlarge
TP_DEGREE=32       # Tensor Parallelism degree (32 is enough for the 8B model)
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
 
# Treat the whole pipeline as failed if the first command fails
set -o pipefail
 
# Compile the model using inference_demo
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


### Step 2-2: Run the compilation

```bash
# Grant execute permission
chmod +x compile_model.sh

# Start compilation
./compile_model.sh
```

**⏱️ Expected duration:**
- First run: 10-30 minutes
- After compilation completes, the model is saved to `~/compiled_models/Qwen3-8B/`

### Step 2-3: Verify compilation success

```bash
# Check the compiled model
ls -lh ~/compiled_models/Qwen3-8B/

# Check the compilation log
tail -50 compile.log
```

**Example output on success:**
```
✅ Compilation complete!
Compiled model saved to: /home/ubuntu/compiled_models/Qwen3-8B/
```



## 3. 🌐 Run the vLLM API server

Once compilation completes, you can run the vLLM server to provide an OpenAI-compatible API.

### Step 3-1: Create the server startup script

**start_vllm.sh:**
```bash
#!/bin/bash

# Neuron runtime settings
export NEURON_RT_INSPECT_ENABLE=0
export NEURON_RT_VIRTUAL_CORE_SIZE=2

# Set the model path (must match the path used during compilation)
MODEL_PATH="/home/ubuntu/models/Qwen3-8B"
COMPILED_MODEL_PATH="/home/ubuntu/compiled_models/Qwen3-8B"

# vLLM environment variables
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

# Run the vLLM server
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

### Step 3-2: Start the server

```bash
# Grant execute permission
chmod +x start_vllm.sh

# Start the server
./start_vllm.sh
```

**⏱️ Server startup time:**
- Loading the compiled model: 1-3 minutes
- Warmup on the first request: 5-15 seconds

### Step 3-3: **⚠️ Important: Parameter descriptions**
- `--max-model-len` = `--seq-len` at compile time
- `--max-num-seqs` = `--batch-size` at compile time
- `--tensor-parallel-size` = `--tp-degree` at compile time

### Step 3-4: Check server status

```bash
# Health check
curl http://localhost:8000/health

# Check the model list
curl http://localhost:8000/v1/models

# Check the server logs
tail -f vllm_server.log
```

**Output on success:**
```json
{"status":"ok"}
```

**Checking the model name:**
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

## 4. 🧪 API Test

Once the server is running, you can test it with the OpenAI-compatible API.

### Step 4-1: cURL test

```bash
# Test the Completion API
curl http://localhost:8000/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "/home/ubuntu/models/Qwen3-8B",
        "prompt": "Explain quantum computing in simple terms:",
        "max_tokens": 256,
        "temperature": 0.7
    }'
```

### Step 4-2: Python client

**test_client.py:**
```python
from openai import OpenAI

# Connect to the vLLM server
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"  # vLLM does not require an API key
)

# Check the models available on the server
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

### Step 4-3: Streaming response test

**test_streaming.py:**
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"
)

# Streaming Chat API
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

## 5. 💡 Additional Tips

### Monitoring

Check NeuronCore utilization in real time:

```bash
# Real-time monitoring
neuron-top

# Detailed information
neuron-monitor

# Monitor a specific process
watch -n 1 neuron-ls
```

### Reusing the compilation cache

The compiled model is saved automatically and reused:

```bash
# Location of the compiled model
ls -lh ~/compiled_models/Qwen3-8B/

# Check the compiled model size
du -sh ~/compiled_models/Qwen3-8B/
```

**Reuse conditions:**
- Use the same `--compiled-model-path`
- The same compilation parameters (tp-degree, batch-size, max-context-length, etc.)
- Set the `NEURON_COMPILED_ARTIFACTS` environment variable

### Using a different storage location

To store the model on NVMe or another location:

```bash
# Download to NVMe (example)
mkdir -p /data/models
huggingface-cli download Qwen/Qwen3-8B \
    --local-dir /data/models/Qwen3-8B \
    --local-dir-use-symlinks False

# Store the compiled model on NVMe too
mkdir -p /data/compiled_models

# Change the paths in the script
MODEL_PATH="/data/models/Qwen3-8B/"
COMPILED_MODEL_PATH="/data/compiled_models/Qwen3-8B/"
```

### Adjusting the log level

Adjust the log level when debugging:

```bash
# Neuron runtime log
export NEURON_RT_LOG_LEVEL=INFO

# More detailed debug information
export NEURON_RT_LOG_LEVEL=DEBUG
export NEURON_RT_INSPECT_ENABLE=1
```

### Running in the background

Run the server in the background:

```bash
# Run in the background with nohup
nohup ./start_vllm.sh > vllm_server.log 2>&1 &

# Check the process
ps aux | grep vllm

# Check the logs
tail -f vllm_server.log

# Stop the server
pkill -f "vllm.entrypoints.openai.api_server"
```

## Summary

With this guide, you can successfully run the Qwen3 8B Instruct model on AWS Trainium2:

1. ✅ **Environment setup**: Activate the vLLM 0.13 Neuron virtual environment
2. ✅ **Model download**: Download the 16 GB model from Hugging Face
3. ✅ **Model compilation**: Compile with inference_demo in 10-30 minutes
4. ✅ **Server launch**: Start the vLLM API server with the compiled model
5. ✅ **API test**: Test inference with the OpenAI-compatible API

**If you run into problems:**
- Check the server logs (`tail -f vllm_server.log`)
- Monitor NeuronCores (`neuron-top`)
- Check the compilation log (`tail -f compile.log`)

**Next steps:**
- Performance optimization: tune TP degree, batch size, and context length
- Production deployment: set up a load balancer and autoscaling
