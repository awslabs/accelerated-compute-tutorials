!!! warning "Classic Guide"
    This document is a guide based on NxD Inference (Maintenance Mode).
    For new deployments, we recommend the [vLLM Neuron Plugin](../vllm/index.md).

# Serving Llama3.1 70B Instruct on Trainium2 with vLLM + NxDI

This guide explains how to serve the [**Llama3.1 70B Instruct**](https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct) model on an **AWS Trainium2 `trn2.48xlarge`** instance using **vLLM 0.13 + NeuronX Distributed Inference (NxDI)**.

It is based on the [Llama 3.3 70B guide](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/libraries/nxd-inference/tutorials/trn2-llama3.3-70b-tutorial.html) in the official AWS Neuron documentation, adapted for Llama 3.1 70B.

**Model Information:**
- **Model**: meta-llama/Llama-3.1-70B-Instruct
- **Parameters**: 70B
- **License**: Llama 3.1 Community License (Gated Model)
- **Context length**: Up to 128K (actual usage is constrained by hardware)

**⚠️ Important: Instance used**
- Llama 3.1 70B is roughly a 140 GB model, so it **runs on trn2.48xlarge (64 NeuronCores)**
- trn2.48xlarge has 64 logical cores (4 NeuronCores × 16)

## ✅ Prerequisites

Before you begin, make sure of the following.

1. **Instance running:** The `trn2.48xlarge` (64 NeuronCores) instance must be active (`Running`).

2. **Use a DLAMI:** The Hugging Face Neuron Deep Learning AMI or the AWS Deep Learning AMI (Neuron) is recommended.
   * Neuron SDK 2.27.1 or later required
   * Includes the vLLM 0.13 Neuron virtual environment

3. **Hugging Face authentication:**
   * Llama3.1 is a gated model, so access permission is required
   * Request access at https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct

4. **(Optional) High-speed storage setup:**
   * To speed up model downloads and caching, you can consider using local NVMe SSD (RAID 0).

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

### Step 1-3: Hugging Face authentication

```bash
# Log in to the Hugging Face CLI
huggingface-cli login

# Enter your token, then verify
huggingface-cli whoami
```

### Step 1-4: Download the model

Download the model ahead of time to the location you want.

```bash
# Create the model storage directory
mkdir -p ~/models
cd ~/models

# Download the Llama3.1 70B Instruct model
huggingface-cli download meta-llama/Llama-3.1-70B-Instruct \
    --local-dir Llama-3.1-70B-Instruct

# Verify the download
ls -lh Llama-3.1-70B-Instruct/
```

**Expected download size:** ~140 GB

**Download time:** 10-30 minutes depending on network speed

## 2. 🔧 Stage 1: Compile the model

Use the `inference_demo` tool to compile the model. This runs only once on the first execution, and the compiled model is reused.

**🔄 How to run:**

This guide describes the **recommended approach (a two-stage process)**:
1. **Compile the model** (once on first run, takes 20-50 minutes) - explicit compilation makes debugging easier
2. **Run the vLLM server** (reuses the compiled model) - fast restart (1-3 minutes)

**💡 Quick Start (automatic compilation):**

```bash
# Set environment variables
export VLLM_NEURON_FRAMEWORK="neuronx-distributed-inference"

# Run the vLLM server (compiles automatically on first run, takes 20-50 minutes)
python -m vllm.entrypoints.openai.api_server \
    --model /home/ubuntu/models/Llama-3.1-70B-Instruct \
    --tensor-parallel-size 64 \
    --max-num-seqs 1 \
    --max-model-len 16384 \
    --block-size 16 \
    --port 8000
```

**Notes:**
- `--device neuron` is not supported in vLLM 0.13 (auto-detected)
- Write the optimization settings as a single line of JSON (no line breaks)
- The compiled model is saved automatically and reused

That said, **pre-compilation is strongly recommended in production environments**:
- Easier debugging if compilation fails
- Shorter server startup time (1-3 minutes)
- Compilation logs can be reviewed clearly
- AWS official recommendation

## Summary

With this guide, you can successfully run the Llama 3.1 70B Instruct model on AWS Trainium2:
1. ✅ **Environment setup**: Activate the vLLM 0.13 Neuron virtual environment
2. ✅ **Model download**: Download the 140 GB model from Hugging Face
3. ✅ **Server launch**: Compile and start the server with a unified command
4. ✅ **API test**: Test inference with the OpenAI-compatible API

**Key points:**
- The v1 plugin approach unifies compilation and execution into a single command
- All optimization options are passed through `--override-neuron-config`
