# vLLM + NxDI (Classic)

A collection of NxD Inference-based vLLM serving guides (SDK 2.31 and earlier).

!!! warning "Maintenance Mode"
    NxD Inference entered Maintenance Mode as of Neuron SDK 2.32.
    For new deployments, we recommend the [vLLM Neuron Plugin](../vllm/index.md).
    For migrating existing NxDI-based deployments, see the [official documentation](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/libraries/nxd-inference/index.html).

## Serving Guides by Model

| Model | Parameters | Instance | TP | Guide |
|------|---------|----------|-----|--------|
| Llama 3.1 70B Instruct | 70B | trn2.48xlarge | 64 | [Open](llama3.1-70b.md) |
| Qwen2.5 72B Instruct | 72B | trn2.48xlarge | 64 | [Open](qwen2.5-72b.md) |
| Qwen3 32B Dense (BF16) | 32B | trn2.48xlarge | 32 | [Open](qwen3-32b.md) |
| Qwen3 8B | 8B | trn2.48xlarge | 32 | [Open](qwen3-8b.md) |
| Qwen3 Coder 480B (A35B) | 480B (35B active) | trn2.48xlarge | 64 | [Open](qwen3-coder-480b.md) |
| Llama 3.1 8B (trn1) | 8B | trn1.32xlarge | 2 | [Open](llama3.1-8b-trn1.md) |

## Common Environment

- **Neuron SDK**: 2.27.1 - 2.31.x
- **vLLM**: 0.13.x (NxDI plugin)
- **Framework**: NeuronX Distributed Inference (NxDI)
- **AMI**: Deep Learning AMI Neuron (Ubuntu 24.04)

## vLLM Neuron Plugin (New) vs. NxDI (Classic)

| Item | vLLM Neuron Plugin (New) | vLLM + NxDI (Classic) |
|------|--------------------------|----------------------|
| SDK version | 2.32+ | 2.27 - 2.31 |
| vLLM version | 0.24+ | 0.13 |
| Model implementation | Inside the plugin (implemented directly) | NxDI library |
| Adding a model | Can be added directly via the onboarding process | Requires implementation by the NxDI team |
| Status | Active Development | Maintenance Mode |
