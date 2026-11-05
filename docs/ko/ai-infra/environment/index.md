---
title: AI 인프라 구축/환경구성
---

# AI 인프라 구축/환경구성

대규모 GPU 학습 환경을 구성하는 기술 요소별 가이드입니다. 호스트 구성부터 스케줄러, 컨테이너, 스토리지, 검증까지 순서대로 다룹니다.

<div class="grid cards" markdown>

-   :material-server:{ .lg .middle } **DLAMI 호스트 구성·검증**

    ---

    Deep Learning AMI 기반 GPU 호스트 구성과 드라이버·EFA·GDS 검증.

    [:octicons-arrow-right-24: DLAMI 호스트 구성·검증](dlami-host-setup.md)

-   :material-calendar-check:{ .lg .middle } **Slurm + Pyxis + Enroot**

    ---

    스케줄러와 컨테이너 런타임 구성, 잡 제출 옵션.

    [:octicons-arrow-right-24: Slurm + Pyxis + Enroot](slurm-pyxis-enroot.md)

-   :material-docker:{ .lg .middle } **컨테이너 이미지 (NGC + EFA)**

    ---

    NGC 이미지에 EFA를 더한 학습 컨테이너 빌드.

    [:octicons-arrow-right-24: 컨테이너 이미지](container-ngc-efa.md)

-   :material-harddisk:{ .lg .middle } **GDS (GPUDirect Storage)**

    ---

    FSx for Lustre를 GPU 메모리에 직접 연결(GDS over EFA)해 데이터 로딩 가속.

    [:octicons-arrow-right-24: GDS](gds-gpudirect-storage.md)

-   :material-check-decagram:{ .lg .middle } **분산 학습 검증 (nccl-tests)**

    ---

    본 학습 전 go/no-go 성능 기준선 측정.

    [:octicons-arrow-right-24: 분산 학습 검증](slurm-pyxis-enroot.md#distributed-training-validation)

-   :material-ethernet:{ .lg .middle } **EFA 네트워크 심화**

    ---

    노드 간 통신 원리와 NCCL 플러그인 검증.

    [:octicons-arrow-right-24: EFA 네트워크 심화](../efa-setup.md)

</div>
