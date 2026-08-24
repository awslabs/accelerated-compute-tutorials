---
title: vLLM on Neuron
---

# vLLM on Neuron

vLLM Neuron Plugin을 사용하여 AWS Trainium에서 LLM을 서빙하기 위한 가이드 모음입니다.

---

<div class="grid cards" markdown>

-   :material-puzzle-outline:{ .lg .middle } **모델 온보딩**

    ---

    신규 모델 아키텍처를 vLLM Neuron Plugin에 추가하는 전체 프로세스.
    2-Phase 접근 (NF 조립 → NKI 최적화), 5단계 워크플로우, 아키텍처 Diff 분석 스크립트 포함.

    [:octicons-arrow-right-24: 가이드 보기](model-onboarding.md)

-   :material-chip:{ .lg .middle } **vLLM Neuron Plugin 구조** · 준비 중

    ---

    Plugin 아키텍처, Model Executor 구조, Prefill/Decode 분리, Continuous Batching 동작 방식.

    :octicons-clock-24: 준비 중

-   :material-server-network:{ .lg .middle } **vLLM Upstreaming** · 준비 중

    ---

    vLLM Neuron이 upstream vLLM과 어떻게 통합되는지, Plugin 구조와 분리 전략.

    :octicons-clock-24: 준비 중

-   :material-book-open-variant:{ .lg .middle } **모델별 서빙 레시피** · 준비 중

    ---

    Llama 3.1 70B, Qwen2.5 72B, Qwen3 32B 등 검증된 모델의 서빙 설정과 벤치마크.

    :octicons-clock-24: 준비 중

</div>

---

## 참고 자료

| 리소스 | 링크 |
|--------|------|
| 공식 문서 | [Neuron Docs: vLLM Neuron](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/vllm-neuron/docs/index.html) |
| GitHub | [vllm-project/vllm-neuron](https://github.com/vllm-project/vllm-neuron) |
| NF API 소스 | [vllm_neuron/functional](https://github.com/vllm-project/vllm-neuron/tree/release-0.24.0.1.1.0/vllm_neuron/functional) |
| Model Recipes | [Neuron Docs: Model Recipes](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/vllm-neuron/docs/model-recipes/index.html) |
