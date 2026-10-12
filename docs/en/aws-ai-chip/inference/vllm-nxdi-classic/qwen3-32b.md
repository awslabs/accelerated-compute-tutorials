!!! warning "Classic Guide"
    This document is a guide based on NxD Inference (Maintenance Mode).
    For new deployments, we recommend the [vLLM Neuron Plugin](../vllm/index.md).

# Serving Qwen3 30B BF16 on Trainium2 with vLLM (NxD)

This guide explains how to serve the [**Qwen 3 (32B)**](https://huggingface.co/Qwen/Qwen3-32B) model on an **AWS Trainium2 (`trn2.48xlarge`)** instance using **vLLM** and the **Neuronx Distributed (NxD)** architecture.
It is based on the [Tutorial](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/libraries/nxd-inference/tutorials/sd-inference-tutorial.html) in the official AWS Neuron documentation.

**Quickstart using Docker** It leverages a pre-configured Deep Learning Container (DLC) from the AWS Neuron fork, with vLLM pre-installed.

* In the aws-neuron GitHub [deep-learning-containers](https://github.com/aws-neuron/deep-learning-containers?tab=readme-ov-file#vllm-inference-neuronx) repository, under vllm-inference-neuronx, you can find the vLLM framework version, Neuron SDK version, and ECR Public URL for each container.

* It follows the vLLM V1 approach and deploys the vLLM server based on [vllm-project/vllm-neuron](https://github.com/vllm-project/vllm-neuron). (Available from [Neuron SDK 2.27](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/release-notes/2.27.0/index.html) and later)

* The legacy vLLM V0 approach is scheduled to be deprecated in Neuron SDK 2.28. Announced in [Inference update](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/about-neuron/whats-new.html#id6).
If you are using V0, we recommend considering a migration to V1.

### 📋 Prerequisites

Before you begin, make sure of the following.

1.  **Instance running:** The `trn2.48xlarge` instance must be active (`Running`).
    * 👉 **[Guide: Launching an XC instance based on a Capacity Block](https://github.com/leesjpe/compute-foundation-on-aws/blob/main/ec2/ec2-dlami-neuron.md)**
3.  **(Optional) High-speed storage setup:**
    * To speed up model loading, you can consider using local NVMe SSD (RAID 0).
    * This is useful for development/testing environments or when you restart frequently; for production environments, EBS is sufficient.
    * 👉 **[Guide: High-speed storage setup (NVMe RAID 0)](https://github.com/leesjpe/compute-foundation-on-aws/blob/main/storage/local-nvme-setup.md)**
    * *Note: If you skip this step, make sure the root EBS volume has enough space to store the model.*

### 1. 🐳 Deploying the vLLM server with Docker
#### Step 1-1: Run the Neuron vLLM container

To avoid library dependency conflicts, use the official AWS **Neuron Deep Learning Container (DLC)**.

Use the command below to run the container and enter its shell.
*(If you set up high-speed storage, you can mount `/data`; if you only use EBS, adjust the path to match your situation.)*

```bash
# Run and enter Docker
# -v /data:/data : mount high-speed storage (or the model path)
# -p 8000:8000 : open the API server port

docker run -d -it \
  --privileged \
  -v /home/ubuntu/:/home/ubuntu/ \
  -v /data:/data \
  -p 8000:8000 \
  public.ecr.aws/neuron/pytorch-inference-vllm-neuronx:0.11.0-neuronx-py312-sdk2.27.0-ubuntu24.04
```

#### 📥 Step 1-2: Enter the virtual environment

```bash
docker exec -it <Container ID> bash
```

#### ⚙️ Step 1-3: Run the vLLM server { #step-1-3-vllm-server }

1-3: Model download

```bash
mkdir /home/ubuntu/qwen3_32b_dense_bf16
hf download Qwen/Qwen3-32B --local-dir /home/ubuntu/qwen3_32b_dense_bf16
```

Step 1-3 runs the vLLM server for [Qwen3 32B Model](https://huggingface.co/Qwen/Qwen3-32B) inference, based on BF16.

Step 1-3 takes about 10-15 minutes, and once you see logs like the following, compilation and server startup are complete ☕️

The legacy vLLM V0 approach used VLLM_USE_V1=0, but it is omitted in V1.

```bash
# Set environment variables
export VLLM_NEURON_FRAMEWORK="neuronx-distributed-inference"
export NEURON_COMPILED_ARTIFACTS="/home/ubuntu/qwen3_32b_dense_bf16_artifacts"
export MODEL_ID="/home/ubuntu/qwen3_32b_dense_bf16"

# Run the server (allows external access through port 8000; restricting to a specific IP is recommended)
vllm serve $MODEL_ID \
    --tensor-parallel-size 16 \
    --max-num-seqs 32 \
    --max-model-len 4096 \
    --block-size 32 \
    --host 0.0.0.0 \
    --port 8000
```
<img width="1294" height="545" alt="Screenshot 2025-12-06 at 9 17 48 PM" src="https://github.com/user-attachments/assets/4cf45802-3e9a-4290-b0c0-e5303f384e40" />

Check the vLLM Model ID
```bash
curl http://localhost:8000/v1/models
```

#### 🧪 Step 1-4: Inference test { #step-1-4-inference }

From the **host machine**, run an inference test against the vLLM server running in the container.

```bash
curl http://localhost:8000/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
"model": "/home/ubuntu/qwen3_32b_dense_bf16",
"prompt": "What is machine learning?",
"max_tokens": 100,
"temperature": 0.7
}'
```
<img width="1295" height="216" alt="Screenshot 2025-12-06 at 10 38 58 PM" src="https://github.com/user-attachments/assets/451cf358-9bc8-45ab-bc77-fb491cb57a6d" />

#### 📊 Step 1-5: Performance Benchmarking (via Host) { #step-1-5-benchmarking }

This section explains how to benchmark the vLLM server from the **host machine**. Running the benchmark on the host avoids Python version conflicts and ensures resource isolation.

##### Prerequisites
* The `llmperf` library recommends a **Python 3.8-3.10** environment. To prevent the system's default Python version from being too high (3.11+) or packages from getting tangled, we recommend using a `conda` virtual environment.

This guide explains how to install llmperf when using the pre-installed Neuron virtual environment, instead of a separate virtual environment for llmperf.

```bash
# 1. Download the llmperf source code (git clone)
git clone https://github.com/ray-project/llmperf.git
cd llmperf

# 2. Change the Python version limit (<3.11) to <3.13 in pyproject.toml (using the sed command)
sed -i 's/<3.11/<3.13/g' pyproject.toml

# 3. Install from the modified source (using the -e option)
pip install -e . --no-deps
```

* Version fix: removes the Python upper bound (<3.11) set in llmperf to prevent installation from being rejected in the 3.12.3 environment currently in use.
* --no-deps option: installs while skipping unnecessary version-conflict checks (e.g., Pydantic) between llmperf and packages already installed in the vLLM environment.

After installation completes, run the command below on the host.

```bash
export OPENAI_API_BASE="http://localhost:8000/v1"
export OPENAI_API_KEY=dummy

python token_benchmark_ray.py \
    --model "/home/ubuntu/qwen3_32b_dense_bf16" \
    --mean-input-tokens 128 \
    --stddev-input-tokens 0 \
    --mean-output-tokens 512 \
    --stddev-output-tokens 0 \
    --max-num-completed-requests 10 \
    --timeout 1200 \
    --num-concurrent-requests 1 \
    --results-dir /tmp/results \
    --llm-api openai \
    --additional-sampling-params '{}'

```

<img width="364" height="1172" alt="Screenshot 2025-12-08 at 9 12 32 PM" src="https://github.com/user-attachments/assets/ce17baea-c904-42a4-bf9d-b848db455af5" />



## 2.🖥️ Deploying the vLLM server using the host machine's virtual environment

### Step 2-1: Activate the vLLM V1 virtual environment
```bash
source /opt/aws_neuronx_venv_pytorch_inference_vllm/bin/activate
```

* The subsequent server launch, inference test, and benchmarking steps proceed the same as described in the Docker approach.

[⚙️ Step 1-3: Run the vLLM server](#step-1-3-vllm-server)

[🧪 Step 1-4: Inference test](#step-1-4-inference)

[📊 Step 1-5: Performance Benchmarking (via Host)](#step-1-5-benchmarking)
