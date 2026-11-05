---
title: AI 인프라 오케스트레이션
---

# AI 인프라 오케스트레이션

Amazon EKS에서 AI 워크로드를 실행하는 핸즈온 랩입니다. GPU Operator, 분산 학습을 위한 Ray·KubeRay, 추론 서빙과 라우팅을 위한 NVIDIA Dynamo를 다룹니다.

<div class="grid cards" markdown>

-   :material-kubernetes:{ .lg .middle } **GPU Operator (Private EKS)**

    ---

    프라이빗 EKS 클러스터에 NVIDIA GPU Operator 배포.

    [:octicons-arrow-right-24: GPU Operator (Private EKS)](private-eks-gpu-operator/index.md)

-   :material-server-network:{ .lg .middle } **Ray + EFA on EKS**

    ---

    EKS에서 Ray + EFA 기반 분산 학습 및 서빙.

    [:octicons-arrow-right-24: Ray + EFA on EKS](ray-on-eks-efa/index.md)

-   :material-tune-variant:{ .lg .middle } **KubeRay 기반 Megatron Bridge 파인튜닝**

    ---

    EKS Auto Mode의 g6e.12xlarge 단일 노드에서 KubeRay RayJob으로 Megatron Bridge를 실행해 Qwen3-8B를 LoRA 파인튜닝.

    [:octicons-arrow-right-24: KubeRay 기반 Megatron Bridge 파인튜닝](megatron-kuberay/index.md)

-   :material-call-split:{ .lg .middle } **Disaggregated Inference (Dynamo)**

    ---

    NVIDIA Dynamo + vLLM 기반 Prefill/Decode 분리 서빙 (EKS).

    [:octicons-arrow-right-24: Disaggregated Inference (Dynamo)](dynamo-disaggregated/index.md)

-   :material-routes:{ .lg .middle } **KV-Aware Routing (Dynamo)**

    ---

    g6e.xlarge 2대에서 NVIDIA Dynamo의 KV-aware 라우터와 round-robin 비교 (AWS vLLM DLC, 공유 EFS 볼륨에서 Run:ai Model Streamer로 로딩, DCGM 대시보드).

    [:octicons-arrow-right-24: KV-Aware Routing (Dynamo)](dynamo-kv-routing/index.md)

</div>
