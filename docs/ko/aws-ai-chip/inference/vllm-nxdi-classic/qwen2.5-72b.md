!!! warning "Classic 가이드"
    이 문서는 NxD Inference (Maintenance Mode) 기반 가이드입니다.
    신규 배포는 [vLLM Neuron Plugin](../vllm/index.md)을 권장합니다.

# Serving Qwen2.5 72B instruct on Trainium2 with vLLM (NxD)

이 가이드는 **AWS Trainium2 (`trn2.48xlarge`)** 인스턴스에서 **vLLM**과 **Neuronx Distributed (NxD)** 아키텍처를 사용하여 [**Qwen 2.5 (72B) Instruct**](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct) 모델을 서빙하는 방법을 설명합니다.
aws neuron 공식문서의 [Tutorial](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/libraries/nxd-inference/tutorials/sd-inference-tutorial.html) 을 기반으로 구성 되었습니다. 

**Quickstart using Docker** vLLM이 사전 설치된 AWS Neuron 포크 버전의 사전 구성된 딥 러닝 컨테이너(DLC)를 활용합니다. 

* aws-neuron Github 의 [deep-learning-contianers](https://github.com/aws-neuron/deep-learning-containers?tab=readme-ov-file#vllm-inference-neuronx) 의 vllm-inference-neuronx 에서 컨테이너 별 vLLM Framework 버전, Neuron SDK 버전, ECR Public URL을 확인 할 수 있습니다.

* vLLM V1 방식을 따르며 [vllm-project/vllm-neuron](https://github.com/vllm-project/vllm-neuron) 기반으로 vLLM 서버를 배포합니다. ([Neuron SDK 2.27](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/release-notes/2.27.0/index.html) 버전 이상부터 적용 가능)

* 기존 vLLM V0 방식은 Neuron SDK 2.28 에서 Deprecated 될 예정입니다. [Inference update](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/about-neuron/whats-new.html#id6)에서 공지. 
V0를 사용하고 있다면 V1 으로의 마이그레이션을 고려하시길 권장합니다.  

---
### 📋 Prerequisites (사전 준비)

진행하기 전에 다음 사항들을 확인하세요.

1.  **인스턴스 실행:** `trn2.48xlarge` 인스턴스가 활성화(`Running`) 상태여야 합니다.
    * 👉 **[가이드: Capacity Block 기반 XC 인스턴스 실행](https://github.com/leesjpe/compute-foundation-on-aws/blob/main/ec2/ec2-dlami-neuron.md)** 
3.  **(선택 사항) 고속 스토리지 설정:**
    * 모델 로딩 속도를 높이려면 로컬 NVMe SSD (RAID 0) 사용을 고려할 수 있습니다.
    * 개발/테스트 환경이나 자주 재시작하는 경우 유용하며, 프로덕션 환경에서는 EBS로도 충분합니다.
    * 👉 **[가이드: 고속 스토리지 설정 (NVMe RAID 0)](https://github.com/leesjpe/compute-foundation-on-aws/blob/main/storage/local-nvme-setup.md)**
    * *참고: 이 과정을 건너뛴다면, 루트 EBS 볼륨에 모델을 저장할 충분한 공간이 있는지 확인하세요.*

---

### 1. 🐳 Docker 기반 vLLM 서버 배포
#### Step 1-1: Neuron vLLM 컨테이너 실행

라이브러리 의존성 충돌을 방지하기 위해 AWS 공식 **Neuron Deep Learning Container (DLC)**를 사용합니다.

아래 명령어를 사용하여 컨테이너를 실행하고 내부 쉘로 진입합니다.
*(고속 스토리지를 설정했다면 `/data` 마운트가 가능하며, EBS만 사용한다면 경로는 상황에 맞게 조정하세요.)*

```bash
# Docker 실행 및 진입
# -v /data:/data : 고속 스토리지(또는 모델 경로) 마운트
# -p 8000:8000 : API 서버 포트 개방

docker run -d -it \
  --privileged \
  -v /home/ubuntu/:/home/ubuntu/ \
  -v /data:/data \
  -p 8000:8000 \
  public.ecr.aws/neuron/pytorch-inference-vllm-neuronx:0.13.0-neuronx-py312-sdk2.28.0-ubuntu24.04
```

#### 📥 Step 1-2: 가상환경 진입

```bash
docker exec -it <Container ID> bash
```

#### ⚙️ Step 1-3 vllm server 실행

1-3: Model download

```bash
mkdir /data/models/qwen2.5-72b-instruct
hf download Qwen/Qwen2.5-72B-Instruct --local-dir /data/models/qwen2.5-72b-instruct
```

1-3 는 [Qwen2.5 72B Instruct Model](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct) 추론을 위한 vllm 서버를 실행 합니다. 

1-3 과정은  10~15 소요되며 아래와 같이 로그가 보이면 컴파일 및 서버 시작 완료 ☕️

<img width="819" height="616" alt="Screenshot 2026-03-09 at 6 23 27 PM" src="https://github.com/user-attachments/assets/537c13e0-9641-4630-946a-6032911a8335" />


기존 vLLM V0 방식에서는 VLLM_USE_V1=0 를 사용했지만 V1 에서는 제외 합니다.

```bash
# 환경 변수 설정
export VLLM_NEURON_FRAMEWORK="neuronx-distributed-inference"
export NEURON_COMPILED_ARTIFACTS="/data/models/qwen2.5-72b-instruct"
export MODEL_ID=$NEURON_COMPILED_ARTIFACTS

# 서버 실행 (8000 포트 통한 외부 접속 허용, 특정 IP 로 제한 권장)
vllm serve $MODEL_ID \
    --tensor-parallel-size 16 \
    --max-num-seqs 32 \
    --max-model-len 4096 \
    --block-size 32 \
    --host 0.0.0.0 \
    --port 8000
```

vLLM Model ID 확인
```bash
curl http://localhost:8000/v1/models
```

#### 🧪 Step 1-4: 추론 테스트 (Inference)

**Host Machine**에서 컨테이너에서 실행 중인 vLLM 서버로의 추론 테스트를 수행합니다.

```bash
curl http://localhost:8000/v1/completions \
    -H "Content-Type: application/json" \
    -d '{
"model": "/data/models/qwen2.5-72b-instruct",
"prompt": "What is machine learning?",
"max_tokens": 100,
"temperature": 0.7
}'
```

<img width="833" height="317" alt="Screenshot 2026-03-09 at 6 23 37 PM" src="https://github.com/user-attachments/assets/f9691245-0239-4071-a44f-5324062b9a53" />