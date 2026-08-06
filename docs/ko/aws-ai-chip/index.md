---
title: AWS AI Chip
---

# AWS AI Chip

AWS의 자체 설계 AI 칩인 **Trainium**에서 대규모 AI 워크로드를 실행하기 위한 실전 가이드입니다.

---

<div class="grid cards" markdown>

-   :material-robot:{ .lg .middle } **추론 (Inference)**

    ---

    vLLM, TGI 등 서빙 프레임워크별 배포 가이드. OpenAI 호환 API, 연속 배칭, 추측 디코딩 지원.

    [:octicons-arrow-right-24: 추론 가이드](inference/index.md)

-   :material-school:{ .lg .middle } **학습 (Training)**

    ---

    NxDT, PyTorch Native, Optimum Neuron으로 대규모 모델을 분산 학습. 사전학습부터 LoRA 파인튜닝까지.

    [:octicons-arrow-right-24: 학습 가이드](training/index.md)

-   :material-code-braces:{ .lg .middle } **NKI Kernel**

    ---

    NeuronCore를 직접 프로그래밍하는 커스텀 커널 작성 및 최적화. Python/NumPy 스타일 타일 프로그래밍.

    [:octicons-arrow-right-24: NKI 가이드](nki/index.md)

-   :material-chart-line:{ .lg .middle } **프로파일링**

    ---

    Neuron Explorer 활용 성능 분석. 프레임워크, NKI, 컴파일러, 런타임 모든 영역 커버.

    [:octicons-arrow-right-24: 프로파일링](profiling/index.md)

-   :material-cog:{ .lg .middle } **고급 설정**

    ---

    Logical NeuronCore Config, Mixed Precision 등 하드웨어 레벨 최적화 옵션.

    [:octicons-arrow-right-24: 고급 설정](advanced/index.md)

-   :material-play-circle:{ .lg .middle } **교육 영상**

    ---

    Neuron Core 개념, 아키텍처 이해를 위한 영상 콘텐츠.

    [:octicons-arrow-right-24: 영상 보기](videos/index.md)

</div>

---

!!! tip "시작하기"
    AWS AI Chip을 처음 사용한다면 [:octicons-arrow-right-24: 시작하기](getting-started.md) 페이지를 먼저 확인하세요.
