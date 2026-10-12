---
title: vLLM on Neuron
---

# vLLM on Neuron

A collection of guides for serving LLMs on AWS Trainium using the vLLM Neuron Plugin.

<div class="grid cards" markdown>

-   :material-puzzle-outline:{ .lg .middle } **Model Onboarding**

    ---

    The full process for adding a new model architecture to the vLLM Neuron Plugin.
    Includes the 2-phase approach (NF assembly → NKI optimization), the 5-step workflow, and an architecture diff analysis script.

    [:octicons-arrow-right-24: View guide](model-onboarding.md)

-   :material-chip:{ .lg .middle } **vLLM Neuron Plugin Internals** · Coming soon

    ---

    Plugin architecture, Model Executor structure, prefill/decode separation, and how continuous batching works.

    :octicons-clock-24: Coming soon

-   :material-server-network:{ .lg .middle } **vLLM Upstreaming** · Coming soon

    ---

    How vLLM Neuron integrates with upstream vLLM, and the plugin structure and separation strategy.

    :octicons-clock-24: Coming soon

-   :material-book-open-variant:{ .lg .middle } **Serving Recipes by Model** · Coming soon

    ---

    Serving configurations and benchmarks for validated models such as Llama 3.1 70B, Qwen2.5 72B, and Qwen3 32B.

    :octicons-clock-24: Coming soon

</div>

## References

| Resource | Link |
|--------|------|
| Official documentation | [Neuron Docs: vLLM Neuron](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/vllm-neuron/docs/index.html) |
| GitHub | [vllm-project/vllm-neuron](https://github.com/vllm-project/vllm-neuron) |
| NF API source | [vllm_neuron/functional](https://github.com/vllm-project/vllm-neuron/tree/release-0.24.0.1.1.0/vllm_neuron/functional) |
| Model Recipes | [Neuron Docs: Model Recipes](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/vllm-neuron/docs/model-recipes/index.html) |
