# vLLM + NxDI (Classic)

NxD Inference 기반 vLLM 서빙 가이드 모음 (SDK 2.31 이하)

!!! warning "Maintenance Mode"
    NxD Inference는 Neuron SDK 2.32부터 Maintenance Mode로 전환되었습니다.
    신규 배포는 [vLLM Neuron Plugin](../vllm/index.md)을 권장합니다.
    기존 NxDI 기반 배포의 마이그레이션 가이드는 [공식 문서](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/libraries/nxd-inference/index.html)를 참조하세요.

---

## 모델별 서빙 가이드

| 모델 | 파라미터 | 인스턴스 | TP | 가이드 |
|------|---------|----------|-----|--------|
| Llama 3.1 70B Instruct | 70B | trn2.48xlarge | 64 | [바로가기](llama3.1-70b.md) |
| Qwen2.5 72B Instruct | 72B | trn2.48xlarge | 64 | [바로가기](qwen2.5-72b.md) |
| Qwen3 32B Dense (BF16) | 32B | trn2.48xlarge | 32 | [바로가기](qwen3-32b.md) |
| Qwen3 8B | 8B | trn2.48xlarge | 32 | [바로가기](qwen3-8b.md) |
| Qwen3 Coder 480B (A35B) | 480B (35B active) | trn2.48xlarge | 64 | [바로가기](qwen3-coder-480b.md) |

---

## 공통 환경

- **Neuron SDK**: 2.27.1 ~ 2.31.x
- **vLLM**: 0.13.x (NxDI 플러그인)
- **프레임워크**: NeuronX Distributed Inference (NxDI)
- **AMI**: Deep Learning AMI Neuron (Ubuntu 24.04)

## vLLM Neuron Plugin (신규) vs NxDI (Classic) 차이

| 항목 | vLLM Neuron Plugin (신규) | vLLM + NxDI (Classic) |
|------|--------------------------|----------------------|
| SDK 버전 | 2.32+ | 2.27 ~ 2.31 |
| vLLM 버전 | 0.24+ | 0.13 |
| 모델 구현 위치 | Plugin 내부 (직접 구현) | NxDI 라이브러리 |
| 모델 추가 | 온보딩 프로세스로 직접 추가 가능 | NxDI 팀 구현 필요 |
| 상태 | Active Development | Maintenance Mode |
