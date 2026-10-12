!!! warning "Classic Guide"
    This document is a guide based on NxD Inference (Maintenance Mode).
    For new deployments, we recommend the [vLLM Neuron Plugin](../vllm/index.md).

# Serving Qwen2.5 72B instruct on Trainium2 with vLLM (NxD)

This guide explains how to serve the [**Qwen 2.5 (72B) Instruct**](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct) model on an **AWS Trainium2 (`trn2.48xlarge`)** instance using **vLLM** and the **Neuronx Distributed (NxD)** architecture.
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
  public.ecr.aws/neuron/pytorch-inference-vllm-neuronx:0.13.0-neuronx-py312-sdk2.28.0-ubuntu24.04
```

#### 📥 Step 1-2: Enter the virtual environment

```bash
docker exec -it <Container ID> bash
```

#### ⚙️ Step 1-3: Run the vLLM server

1-3: Model download

```bash
mkdir /data/models/qwen2.5-72b-instruct
hf download Qwen/Qwen2.5-72B-Instruct --local-dir /data/models/qwen2.5-72b-instruct
```

Step 1-3 runs the vLLM server for [Qwen2.5 72B Instruct Model](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct) inference.

Step 1-3 takes about 10-15 minutes, and once you see logs like the following, compilation and server startup are complete ☕️

<img width="819" height="616" alt="Screenshot 2026-03-09 at 6 23 27 PM" src="https://github.com/user-attachments/assets/537c13e0-9641-4630-946a-6032911a8335" />


The legacy vLLM V0 approach used VLLM_USE_V1=0, but it is omitted in V1.

```bash
# Set environment variables
export VLLM_NEURON_FRAMEWORK="neuronx-distributed-inference"
export NEURON_COMPILED_ARTIFACTS="/data/models/qwen2.5-72b-instruct"
export MODEL_ID=$NEURON_COMPILED_ARTIFACTS

# Run the server (allows external access through port 8000; restricting to a specific IP is recommended)
vllm serve $MODEL_ID \
    --tensor-parallel-size 16 \
    --max-num-seqs 32 \
    --max-model-len 4096 \
    --block-size 32 \
    --host 0.0.0.0 \
    --port 8000
```

Check the vLLM Model ID
```bash
curl http://localhost:8000/v1/models
```

#### 🧪 Step 1-4: Inference test

From the **host machine**, run an inference test against the vLLM server running in the container.

```bash
curl http://localhost:8000/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
"model": "/data/models/qwen2.5-72b-instruct",
"prompt": "What is machine learning?",
"max_tokens": 100,
"temperature": 0.7
}'
```

<img width="833" height="317" alt="Screenshot 2026-03-09 at 6 23 37 PM" src="https://github.com/user-attachments/assets/f9691245-0239-4071-a44f-5324062b9a53" />
