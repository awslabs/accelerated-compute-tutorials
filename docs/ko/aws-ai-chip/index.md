---
title: Trainium
---

# AWS Trainium

AWS가 자체 설계한 AI 칩인 **AWS Trainium** 에서 대규모 AI 워크로드를 실행하기 위한 실전 가이드입니다. Trainium은 GPU와 함께 선택할 수 있는 강력한 가속기 옵션으로, 학습과 추론 모두에서 뛰어난 가격 대비 성능을 내도록 설계되었습니다.

Trainium은 셀프 매니지드 인프라 — Amazon EKS, Amazon ECS, AWS Batch, Amazon EC2 — 또는 Amazon SageMaker에서 사용할 수 있습니다.

<div class="grid cards" markdown>

-   :material-robot:{ .lg .middle } **추론 (Inference)**

    ---

    서빙 프레임워크(vLLM, TGI)별 배포 가이드. OpenAI 호환 API, 연속 배칭, 추측 디코딩.

    [:octicons-arrow-right-24: 추론 가이드](inference/index.md)

-   :material-school:{ .lg .middle } **학습 (Training)**

    ---

    NxDT, PyTorch Native, Optimum Neuron을 활용한 대규모 모델 분산 학습 — 사전학습부터 LoRA 파인튜닝까지.

-   :material-code-braces:{ .lg .middle } **NKI 커널**

    ---

    Python/NumPy 스타일 타일 프로그래밍으로 NeuronCore를 직접 프로그래밍하는 커스텀 커널 작성 및 최적화.

    [:octicons-arrow-right-24: NKI 커널](profiling/nki-kernels.md)

-   :material-chart-line:{ .lg .middle } **프로파일링**

    ---

    Neuron Explorer를 활용한 성능 분석 — 프레임워크, NKI, 컴파일러, 런타임 레이어 전반.

    [:octicons-arrow-right-24: 프로파일링 가이드](profiling/index.md)

-   :material-cog:{ .lg .middle } **고급 설정**

    ---

    Logical NeuronCore 구성, 혼합 정밀도(Mixed Precision) 등 하드웨어 레벨 최적화 옵션.

-   :material-play-circle:{ .lg .middle } **교육 영상**

    ---

    NeuronCore 개념과 아키텍처에 관한 영상 콘텐츠.

</div>
