!!! warning "Classic Guide"
    This document is a guide based on NxD Inference (Maintenance Mode).
    For new deployments, we recommend the [vLLM Neuron Plugin](../vllm/index.md).

# Qwen3-Coder-480B Inference on AWS Trainium2 (Trn2) with vLLM

This guide explains how to serve and run inference for the [Qwen3-Coder-480B-A35B-Instruct](https://huggingface.co/Qwen/Qwen3-Coder-480B-A35B-Instruct) model on an **AWS Trainium2 (Trn2)** instance using **vLLM**.

This guide supports the MoE (Mixture of Experts) architecture and includes settings optimized for the Neuron SDK.

## 📋 Prerequisites

Before running this guide, you must complete **EC2 instance creation and storage setup**.
A high-performance storage configuration is recommended for handling the large (480B) model.

- **[Creating an EC2 instance](https://github.com/leesjpe/compute-foundation-on-aws/blob/main/ec2/ec2-dlami-neuron.md) and [mounting high-performance storage (RAID 0)](https://github.com/leesjpe/compute-foundation-on-aws/blob/main/storage/local-nvme-setup.md)**
- **Recommended instance:** `trn2.48xlarge`
- **Required storage:** An NVMe/EBS volume of at least 4 TB mounted at the `/data` path

## 🛠️ 1. Environment setup and dependency check

Activate the AWS Neuron vLLM virtual environment and check the versions.

```bash
# Activate the virtual environment
source /opt/aws_neuronx_venv_pytorch_inference_vllm_0_13/bin/activate

# Check the key package versions
pip list | grep neuron
```

### ✅ Tested Environment Versions
This guide was tested on the versions below.

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

## 📥 2. Download the model

Use the Hugging Face CLI to download the model to the `/data` directory.
Run it in the foreground so you can monitor the download directly in the terminal.

> **Note:** The model is very large (about 1 TB), so the download can take a considerable amount of time.

```bash
# 1. Set repository permissions (/data path)
sudo chown -R ubuntu:ubuntu /data
mkdir -p /data/models/qwen3-coder-480b-a35b-instruct

# 2. Run the model download
# --local-dir-use-symlinks False: stores the actual files at that path instead of in the cache.
huggingface-cli download Qwen/Qwen3-Coder-480B-A35B-Instruct \
--local-dir /data/models/qwen3-coder-480b-a35b-instruct \
--local-dir-use-symlinks False
```

## 🚀 3. Run the vLLM server (Server Serving)

Run the API server with settings optimized for the Neuron SDK.
It includes an `additional-config` for the Qwen3 MoE model.

> **Note:** On the first run, model compilation and loading can take tens of minutes until the server is ready (`Uvicorn running...`).

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

<img width="1067" height="801" alt="Screenshot 2026-01-28 at 10 39 59 AM" src="https://github.com/user-attachments/assets/4cc59b6f-5351-4222-9bda-12fdc26a72e6" />


## 🧪 4. Inference test (Tool Calling Demo)

Once the server is running correctly, test the tool calling feature with the Python script below.
To avoid vLLM server option constraints, it uses a **prompt engineering (system prompt)** approach to elicit JSON output.

### Writing `test_inference.py`

```python
from openai import OpenAI
import json

# 1. Configure the client
client = OpenAI(
    base_url='http://localhost:8000/v1', 
    api_key="EMPTY"
)

# 2. Convert the tool definitions into a 'text prompt'
# Using the API's tools parameter can cause conflicts with the server settings, so we inject them via the system prompt.
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

# 3. Send the request
print("Thinking (Prompt Engineering Mode)...")

messages = [
    {'role': 'system', 'content': system_instruction},
    {'role': 'user', 'content': 'square the number 1024'}
]

completion = client.chat.completions.create(
    model="/data/models/qwen3-coder-480b-a35b-instruct", # the model path specified when starting the server
    messages=messages,
    # ★ Important: remove the tools parameter and control via the prompt
    max_tokens=1024,
    temperature=0.0, 
)

# 4. Check and parse the result
response_text = completion.choices[0].message.content
print(f"▼ Model response (Raw Text):")
print(response_text)

# Attempt to parse as JSON (verify the model responded as intended)
try:
    if "{" in response_text:
        # Extract only the JSON portion
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        tool_call_json = json.loads(response_text[json_start:json_end])
        
        print("\n▼ Success! The model generated a tool call JSON:")
        print(json.dumps(tool_call_json, indent=2))
    else:
        print("\n▼ The model did not generate JSON.")
except Exception as e:
    print(f"\n▼ Parsing error: {e}")
```

### Running the test

```bash
python3 test_inference.py
```
<img width="800" height="906" alt="Screenshot 2026-01-28 at 10 43 13 AM" src="https://github.com/user-attachments/assets/ff42a804-713b-4738-a602-2032c03cf736" />


## 📝 Appendix:
