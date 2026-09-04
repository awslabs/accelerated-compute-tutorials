# Distributed Fine-tuning and Inference on Amazon EKS with Ray + EFA — Lab Guide

This hands-on lab runs **distributed LLM fine-tuning** and **distributed LLM inference** on Amazon EKS using **KubeRay** (the Ray Kubernetes operator) across **2× p5.48xlarge** GPU nodes connected by **Elastic Fabric Adapter (EFA)**. Compute is provisioned by **EKS Auto Mode**, which manages nodes with Karpenter and ships the NVIDIA GPU drivers/device plugin out of the box. Ray schedules work across all **16 NVIDIA H100 GPUs** (8 per node), and cross-node collective communication — gradient all-reduce during training and tensor-parallel all-reduce during inference — runs over **NCCL on EFA** instead of TCP.

Target region: **us-east-2**. GPUs: **2× p5.48xlarge** (8× NVIDIA H100 80 GB per node = 16 GPUs total), provisioned from an **EC2 Capacity Block for ML** and pinned to a single Availability Zone (us-east-2b) because EFA traffic is AZ-local.

> This lab follows the Ray [Amazon EKS for KubeRay guide](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/aws-eks-gpu-cluster.html) and AWS's [Manage EFA devices on Amazon EKS](https://docs.aws.amazon.com/eks/latest/userguide/device-management-efa.html) (Auto Mode section) and [Control deployment of workloads into Capacity Reservations](https://docs.aws.amazon.com/eks/latest/userguide/auto-odcr.html). No Terraform or cluster-blueprint clone required — just `eksctl`, `helm`, `kubectl`, and the AWS CLI.

> **Why Auto Mode + EFA needs extra steps.** EKS Auto Mode includes the NVIDIA device plugin (so `nvidia.com/gpu` works with no setup), but it does **not** ship the EFA device plugin and does **not** attach EFA interfaces on its built-in NodeClass. So this lab: (1) defines a **custom NodeClass** that attaches EFA interfaces at launch and pins to the Capacity Block, (2) adds a **static-capacity NodePool** (`replicas: 2`, `capacity-type: reserved`) for the p5.48xlarge workers, and (3) **installs the EFA device plugin** via Helm to expose `vpc.amazonaws.com/efa`.

> **Static capacity is required for EFA on Auto Mode.** When a NodeClass statically defines EFA interfaces (`advancedNetworking.networkInterfaces`), EKS Auto Mode does **not** scale that pool dynamically from zero based on pending pods. The GPU NodePool must be a [static capacity node pool](https://docs.aws.amazon.com/eks/latest/userguide/auto-static-capacity.html) (`replicas` set, only `limits.nodes` allowed). This is why the `gpu-efa` NodePool in this lab uses `replicas: 2`.

---

## What is Ray on Kubernetes with EFA?

**Ray** is a distributed compute framework. **KubeRay** runs Ray clusters on Kubernetes through three custom resources:

| Resource | Purpose | Used in this lab for |
|----------|---------|----------------------|
| **RayCluster** | A long-lived Ray cluster (1 head + N workers) | The shared GPU cluster for fine-tuning |
| **RayJob** | Runs a job, optionally against a RayCluster, then (optionally) tears it down | Distributed LoRA fine-tuning |
| **RayService** | A Ray Serve application with its own managed RayCluster + zero-downtime upgrades | OpenAI-compatible LLM inference |

**EFA** is an AWS network interface with OS-bypass and RDMA (via the SRD protocol). For multi-node GPU workloads, EFA lets **NCCL** — the library PyTorch/vLLM use for GPU-to-GPU collective communication — move data between nodes at high bandwidth and low latency, which is what makes multi-node training and tensor parallelism scale.

### Why EFA matters here

- **Fine-tuning** does a gradient **all-reduce** every step across all 16 GPUs. When those GPUs span two nodes, the cross-node hop is on the network — EFA keeps it fast.
- **Inference** uses `tensor_parallel_size=8` within each node (NVLink) and `pipeline_parallel_size=2` across the two nodes. The cross-node pipeline hop sends stage activations over EFA — a lighter, more efficient pattern than cross-node tensor-parallel all-reduce.
- Without EFA, NCCL falls back to TCP and cross-node steps become a bottleneck.

### The EFA software stack (how the pieces fit)

Getting NCCL to actually use EFA requires a specific stack of components, split
between what the **host AMI** provides, what the **custom image** provides, and
what **Kubernetes/EKS** wires up. A missing layer causes a silent fall back to
TCP. This diagram shows the full dependency chain for one Ray worker pod:

```
   ┌──────────────────────────────────────────────────────────────────────┐
   │  Application:  PyTorch (fine-tune)  /  vLLM (inference)              │
   │      │  calls collective ops (all-reduce, all-gather, ...)           │
   │      ▼                                                               │
   │  NCCL  (libnccl.so)                    ← GPU collective comm library │
   │      │  picks a "net" transport plugin at init                       │
   │      │  env: NCCL_NET_PLUGIN, NCCL_TUNER_PLUGIN, NCCL_DEBUG=INFO     │
   │      ▼                                                               │
   │  aws-ofi-nccl  (libnccl-net.so ─► libnccl-net-ofi.so)                │  ── in the
   │      │  the NCCL↔libfabric shim ("NET/OFI"). If ABSENT, NCCL uses    │     custom
   │      │  its built-in NET/Socket (TCP) transport instead.             │     image
   │      ▼                                                               │  (Dockerfile.efa,
   │  libfabric  (/opt/amazon/efa/lib/libfabric.so)                       │   built from
   │      │  OS-bypass fabric API; selects the "efa" provider             │   aws-efa-installer
   │      │  env: FI_PROVIDER=efa, FI_EFA_USE_DEVICE_RDMA=1               │   + aws-ofi-nccl)
   │      ▼                                                               │
   │  EFA provider (efa-direct) → rdma-core / libibverbs (userspace verbs)│
   └──────────────────────────────────────────────────────────────────────┘
          │  ioctl / uverbs
          ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │  EFA kernel driver (ib_uverbs, efa.ko)   ← provided by the HOST AMI  │
   │      │                                     (Bottlerocket EKS-Nvidia);│
   │      ▼                                     NOT installed in-container│
   │  /dev/infiniband/uverbs0..7   ← 8 EFA devices exposed into the pod   │
   └──────────────────────────────────────────────────────────────────────┘
          │  DMA / SRD over the wire
          ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │  EFA network interfaces (NICs)  — 8x efa-only ENIs on p5.48xlarge    │
   │  attached at launch by the NodeClass advancedNetworking.networkIfaces│
   └──────────────────────────────────────────────────────────────────────┘

   Kubernetes / EKS wiring (makes the above schedulable):

   • NodeClass  (advancedNetworking.networkInterfaces) → attaches 1 ENI + 8 efa-only
                 ENIs at launch; capacityReservationSelectorTerms pins the Capacity Block
   • NodePool   (static replicas: 2, capacity-type: reserved) → holds 2x p5.48xlarge
   • EFA device plugin (DaemonSet) → advertises  vpc.amazonaws.com/efa: 8  as a
                 schedulable resource; the pod REQUESTS it in resources.limits
   • NVIDIA device plugin (built into Auto Mode) → advertises  nvidia.com/gpu: 8
   • Security groups → cluster SG (kubelet↔API) + self-referencing EFA SG (RDMA)
   • hugepages-2Mi + /dev/shm (emptyDir Memory) → required by the libfabric/EFA stack
```

**Who provides what:**

| Layer | Component | Source |
|-------|-----------|--------|
| App | PyTorch / vLLM | pip (runtime env or baked into image) |
| Collectives | NCCL (`libnccl.so`) | bundled in the Ray GPU base image |
| NCCL↔fabric shim | **aws-ofi-nccl** (`libnccl-net.so`) | **built in `Dockerfile.efa`** (v1.13.2-aws) |
| Fabric API | **libfabric** (`efa` provider) | **`aws-efa-installer` in `Dockerfile.efa`** |
| Userspace verbs | rdma-core / libibverbs | EFA installer |
| Kernel driver | `efa.ko`, `ib_uverbs` | **host AMI** (Bottlerocket EKS-Nvidia) |
| Device nodes | `/dev/infiniband/uverbs*` | host, surfaced into pod |
| K8s resource | `vpc.amazonaws.com/efa` | **EFA device plugin** (Helm, Step 3) |
| ENIs | 1 primary + 8 efa-only | **NodeClass** `advancedNetworking` (Step 2/3.5) |

The two layers this lab has to add itself (everything else is provided by the
base image, host AMI, or Auto Mode) are the **aws-ofi-nccl + libfabric** stack
(the custom image, Step 3.5) and the **EFA device plugin** (Step 3). Miss either
and NCCL reports `NET/Socket` instead of `NET/OFI ... Selected provider is efa`.

---

## Architecture

```
                    Amazon EKS Auto Mode (us-east-2, single AZ)
┌────────────────────────────────────────────────────────────────────────┐
│                                                                        │
│   ┌─────────────────────────────┐   built-in general-purpose NodePool  │
│   │  KubeRay operator           │   (CPU, Auto Mode managed)           │
│   │  Ray head  :8265 dashboard  │   ← no GPUs on the head (Ray best    │
│   │            :8000 Serve      │     practice); hosts operator+head   │
│   └──────────────┬──────────────┘                                      │
│                  │ Ray GCS / scheduling                                │
│          ┌───────┴────────┐        custom gpu-efa NodePool + NodeClass │
│          ▼                ▼        (2× p5.48xlarge, Capacity Block,    │
│   ┌──────────────┐   ┌──────────────┐  8 EFA IFs at launch)            │
│   │ Ray worker 0 │   │ Ray worker 1 │  taint ray.io/node-type=worker   │
│   │ 8× H100 GPU  │◀═▶│ 8× H100 GPU  │                                  │
│   │ EFA (8 IF)   │NCCL│ EFA (8 IF)  │  NCCL all-reduce over EFA/SRD    │
│   │ hugepages    │over│ hugepages   │  (training grads + TP inference) │
│   └──────────────┘EFA └──────────────┘                                 │
│                                                                        │
│   nvidia.com/gpu : built into Auto Mode                                │
│vpc.amazonaws.com/efa : from the EFA device plugin (installed in Step 3)│
│                                                                        │
│   Fine-tune: RayJob → TorchTrainer, 16 workers × 1 GPU (data parallel) │
│   Inference: RayService → Ray Serve LLM + vLLM, TP=8 x PP=2 (16 GPU) │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

- **AWS CLI**, **kubectl** (v1.30+), **eksctl** (v0.200.0+ for Auto Mode support), and **Helm** (v3+) installed.
- An AWS account in **us-east-2** with a purchased **EC2 Capacity Block for ML** covering **2× p5.48xlarge** in a single AZ (this lab uses us-east-2b). Capacity Blocks are the reliable way to get P5 capacity; find and purchase one with `aws ec2 describe-capacity-block-offerings` / `aws ec2 purchase-capacity-block`. You also need quota for **P-instance vCVPUs** (2× p5.48xlarge = **384 vCPUs** of "Running On-Demand P instances") if you ever run these outside a Capacity Block.
- **No Hugging Face token required** — both the fine-tuning model (`Qwen/Qwen3-4B`) and the inference model (`Qwen/Qwen3-32B`) are ungated/public. (To use a gated model such as `meta-llama/Llama-3.2-1B`, create the `hf-token` secret and propagate `HF_TOKEN` to the Ray workers — see `finetune-rayjob.yaml`.)

> **EFA note.** p5.48xlarge exposes up to **32 EFA interfaces** across 32 network cards (`MaximumEfaInterfaces=32`). This lab configures **8 EFA interfaces** (1 primary `interface` + 8 `efa-only`, cards 1–8) and each Ray worker requests `vpc.amazonaws.com/efa: 8`. On **Auto Mode**, EFA interfaces are attached at launch by the custom **NodeClass** (`advancedNetworking.networkInterfaces`), and the `vpc.amazonaws.com/efa` resource is advertised by the **EFA device plugin** you install in Step 3. The NVIDIA device plugin is already built into Auto Mode. EFA cannot cross Availability Zones, so the GPU NodePool is pinned to the **Capacity Block AZ** via the NodeClass subnet selector. EFA also requires **hugepages** and a large **`/dev/shm`**, both configured in the Ray worker pods.

> **Two gotchas with statically-defined EFA interfaces on Auto Mode (both handled in this lab's NodeClass):**
> 1. **Security groups.** The EFA nodes need BOTH the **EKS cluster security group** (so the kubelet can reach the API server and register — otherwise nodes launch, fail to join, and are terminated in a loop) **and** the **EFA self-referencing security group** (for RDMA). `securityGroupSelectorTerms` selects both.
> 2. **Pod IPs.** With static `networkInterfaces`, Auto Mode does **not** add IPs after launch, so the primary ENI must pre-allocate a pod IP pool via `secondaryIPv4PrefixCount` — otherwise pods fail with `failed to assign an IP address to container`.

> **Static capacity note.** Because the NodeClass statically defines EFA interfaces, the `gpu-efa` NodePool must be a **static capacity node pool** (`replicas: 2`, only `limits.nodes` allowed) — Auto Mode will not scale statically-EFA NodeClasses dynamically from zero. Capacity Blocks are consumed via `karpenter.sh/capacity-type: reserved` plus `capacityReservationSelectorTerms` on the NodeClass.

> **Cost warning.** This lab runs a **Capacity Block for 2× p5.48xlarge** (16× H100). Capacity Blocks are billed **upfront and are non-refundable** for the full reserved window (e.g., ~$739 for an ~8-hour 2-node block, ~$1,993 for 24 hours — prices vary). Plus small Auto Mode general-purpose nodes. Instances auto-terminate at the block's end time; still run the cleanup step when done. Check the [AWS Pricing Calculator](https://calculator.aws/) for current rates.

---

## Step 1 — Create the EKS Auto Mode cluster

```bash
export AWS_REGION="us-east-2"
export CLUSTER_NAME="ray-efa-lab"

# Confirm p5.48xlarge is offered in your target AZ first:
aws ec2 describe-instance-type-offerings --region ${AWS_REGION} \
  --location-type availability-zone \
  --filters Name=instance-type,Values=p5.48xlarge \
  --query 'InstanceTypeOfferings[*].Location' --output text

eksctl create cluster -f manifests/eksctl-cluster.yaml
```

This takes ~15 minutes and enables Auto Mode with its built-in `general-purpose` and `system` NodePools. `kubectl` is configured automatically when it finishes.

```bash
kubectl get nodes           # likely 0 — Auto Mode provisions on demand
kubectl get nodepool        # general-purpose, system (built-in)
```

Capture the **Auto Mode node IAM role** — the custom NodeClass reuses it:

```bash
export NODE_ROLE=$(kubectl get nodeclass default -o jsonpath='{.spec.role}')
echo "Auto Mode node role: ${NODE_ROLE}"
```

---

## Step 2 — Purchase a Capacity Block and prepare EFA networking

First, find and purchase a Capacity Block for 2× p5.48xlarge, and note its AZ and reservation ID:

```bash
# Find offerings (adjust duration/count as needed)
aws ec2 describe-capacity-block-offerings --region ${AWS_REGION} \
  --instance-type p5.48xlarge --instance-count 2 --capacity-duration-hours 24 \
  --query 'CapacityBlockOfferings[].{Id:CapacityBlockOfferingId,AZ:AvailabilityZone,Start:StartDate,End:EndDate,Fee:UpfrontFee}' \
  --output table

# Purchase one (UPFRONT, NON-REFUNDABLE). Capture the reservation ID + AZ.
export CB_OFFERING="cb-xxxxxxxxxxxxxxxxx"   # from the output above
export CR_ID=$(aws ec2 purchase-capacity-block --region ${AWS_REGION} \
  --capacity-block-offering-id ${CB_OFFERING} --instance-platform Linux/UNIX \
  --query 'CapacityReservation.CapacityReservationId' --output text)
export EFA_AZ=$(aws ec2 describe-capacity-reservations --region ${AWS_REGION} \
  --capacity-reservation-ids ${CR_ID} \
  --query 'CapacityReservations[0].AvailabilityZone' --output text)
echo "Capacity Block: ${CR_ID} in ${EFA_AZ}"
```

Put `${CR_ID}` in the NodeClass `capacityReservationSelectorTerms` (see `manifests/automode-nodeclass-efa.yaml`).

EFA needs a security group that allows **all traffic to and from itself**, and single-AZ subnets in the Capacity Block AZ. Auto Mode's NodeClass selects them by tag. **The EFA nodes also need the EKS cluster security group** so the kubelet can reach the API server — the NodeClass selects both.

```bash
export VPC_ID=$(aws eks describe-cluster --name ${CLUSTER_NAME} --region ${AWS_REGION} \
  --query 'cluster.resourcesVpcConfig.vpcId' --output text)

# 1) Create an EFA security group that allows all traffic to/from itself.
export EFA_SG=$(aws ec2 create-security-group --region ${AWS_REGION} \
  --group-name ray-efa-sg --description "EFA self-referencing SG" \
  --vpc-id ${VPC_ID} --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress --region ${AWS_REGION} \
  --group-id ${EFA_SG} --protocol -1 --source-group ${EFA_SG}
aws ec2 authorize-security-group-egress --region ${AWS_REGION} \
  --group-id ${EFA_SG} --protocol -1 --source-group ${EFA_SG}
aws ec2 create-tags --region ${AWS_REGION} --resources ${EFA_SG} \
  --tags Key=efa,Value=true

# NOTE: the NodeClass securityGroupSelectorTerms also selects the EKS cluster
# security group (tagged kubernetes.io/cluster/<cluster-name>=owned). Both SGs
# get attached to each EFA node. Update the tag value in the NodeClass to match
# your cluster name.

# 2) Tag the Capacity Block AZ's private subnet(s) so the NodeClass subnetSelector
#    matches only that AZ (EFA is AZ-local; must match the Capacity Block AZ).
for SUBNET in $(aws ec2 describe-subnets --region ${AWS_REGION} \
  --filters Name=vpc-id,Values=${VPC_ID} \
            Name=availability-zone,Values=${EFA_AZ} \
  --query 'Subnets[?MapPublicIpOnLaunch==`false`].SubnetId' --output text); do
  aws ec2 create-tags --region ${AWS_REGION} --resources ${SUBNET} \
    --tags Key=kubernetes.io/role/efa,Value=1
done
```

Set the node role in the NodeClass, then apply the NodeClass, NodePool, and StorageClass:

```bash
# Substitute the Auto Mode node role captured in Step 1.
sed -i.bak "s|REPLACE_WITH_AUTO_MODE_NODE_ROLE|${NODE_ROLE}|" \
  manifests/automode-nodeclass-efa.yaml

kubectl apply -f manifests/automode-nodeclass-efa.yaml
kubectl apply -f manifests/automode-nodepool-gpu.yaml
kubectl apply -f manifests/auto-ebs-sc.yaml

kubectl get nodeclass gpu-efa
kubectl get nodepool gpu-efa
kubectl get storageclass auto-ebs-sc
```

---

## Step 3 — Install the EFA device plugin

Auto Mode ships the NVIDIA device plugin but **not** the EFA device plugin. Install it so nodes advertise `vpc.amazonaws.com/efa`:

```bash
helm repo add eks https://aws.github.io/eks-charts
helm repo update

helm install efa eks/aws-efa-k8s-device-plugin -n kube-system
```

Verify the DaemonSet (it schedules onto EFA-capable nodes as they appear):

```bash
kubectl get daemonset -n kube-system efa-aws-efa-k8s-device-plugin
# NAME                            DESIRED  CURRENT  READY ...
# efa-aws-efa-k8s-device-plugin   ...
```

`vpc.amazonaws.com/efa` won't show as allocatable until a p5.48xlarge node is running (provisioned from the Capacity Block; the static NodePool holds 2 nodes). NVIDIA GPUs are available with no extra install.

> **The EFA device plugin is necessary but NOT sufficient for NCCL-over-EFA.** It only advertises the `vpc.amazonaws.com/efa` resource so pods can request EFA interfaces. NCCL still needs the **aws-ofi-nccl plugin** (`libnccl-net.so`) inside the container to actually use the EFA/libfabric transport. The stock `rayproject/ray:*-gpu` image does **not** ship it, so NCCL silently falls back to TCP (`NET/Socket`) for cross-node collectives. See Step 3.5.

---

## Step 3.5 — Build the Ray + EFA images (aws-ofi-nccl plugin, and vLLM for inference)

The Ray worker pods use a custom image (`Dockerfile.efa`) that layers the EFA
libfabric stack and the **aws-ofi-nccl** plugin onto a Ray GPU base image.
Without the plugin, NCCL cannot select the EFA transport and cross-node traffic
falls back to TCP.

This lab builds **one image** from `Dockerfile.efa`, used by both the
fine-tuning and inference paths so the whole lab runs on a single Ray version:

| Tag | Base | Contents | Used by |
|-----|------|----------|---------|
| `ray-efa:2.58.0-efa-vllm` | `rayproject/ray:2.58.0-py311-gpu` | EFA + aws-ofi-nccl + **vLLM 0.26.0** | Part A (fine-tuning) **and** Part B (inference) |

```bash
export ECR="<account>.dkr.ecr.${AWS_REGION}.amazonaws.com"
aws ecr create-repository --region ${AWS_REGION} --repository-name ray-efa || true
aws ecr get-login-password --region ${AWS_REGION} \
  | docker login --username AWS --password-stdin ${ECR}

# Single image for the whole lab. INSTALL_VLLM defaults to true.
# Build for amd64 (the p5.48xlarge nodes) and push.
docker buildx build --platform linux/amd64 -f Dockerfile.efa \
  -t ${ECR}/ray-efa:2.58.0-efa-vllm --push .
```

The Dockerfile:
1. Installs the AWS EFA software stack (libfabric) via the EFA installer (`--skip-kmod`, the host AMI provides the kernel driver).
2. Builds **aws-ofi-nccl** (`v1.13.2-aws`) from source against the image's system NCCL/CUDA and the EFA libfabric, installing `libnccl-net-ofi.so` / `libnccl-tuner-ofi.so` into `/opt/amazon/ofi-nccl`.
3. Symlinks them to the canonical `libnccl-net.so` / `libnccl-ofi-tuner.so` names NCCL expects.
4. Installs `ray[data,llm,serve]==2.58.0` + `vllm==0.26.0` in one pip pass so the resolver reconciles them (this is what makes the inference path work without a runtime Ray-version conflict). Set `--build-arg INSTALL_VLLM=false` for a smaller training-only image on the same Ray 2.58.0 base.

All manifests (`ray-cluster-efa.yaml`, `inference-rayservice.yaml`) reference this single `${ECR}/ray-efa:2.58.0-efa-vllm` image for head and workers, and set `rayVersion: "2.58.0"`. The worker pods set `NCCL_NET_PLUGIN`, `NCCL_TUNER_PLUGIN`, `FI_PROVIDER=efa`, and `LD_LIBRARY_PATH` so NCCL loads the plugin. Because head and workers share the image, the cluster's Ray version is consistent and no runtime_env pip install is needed.

---

## Step 4 — Install the KubeRay operator

```bash
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm repo update

helm install kuberay-operator kuberay/kuberay-operator \
  --version 1.7.0 \
  --namespace kuberay-system --create-namespace
```

Verify:

```bash
kubectl get pods -n kuberay-system
# kuberay-operator-xxxxxxxxxx-xxxxx   1/1   Running

kubectl get crds | grep ray.io
# rayclusters.ray.io  rayjobs.ray.io  rayservices.ray.io
```

The operator runs on an Auto Mode general-purpose node.

---

## Part A — Distributed fine-tuning

### Step 5 — (Optional) Create the Hugging Face token secret

Required only for gated models (the default fine-tuning model is gated):

```bash
export HF_TOKEN="hf_xxxxxxxxxxxxxxxxxxxxx"  # your token

kubectl create secret generic hf-token \
  --from-literal=HF_TOKEN=${HF_TOKEN}
```

The fine-tuning submitter reads this secret with `optional: true`, so you can skip it if you switch to an ungated model.

### Step 6 — Deploy the RayCluster

```bash
kubectl apply -f manifests/ray-cluster-efa.yaml

# The static gpu-efa NodePool provisions 2× p5.48xlarge from the Capacity
# Block; first start is slow
# (node boot + large image pull). Watch nodes and pods appear:
kubectl get nodes -w
kubectl get raycluster ray-efa
kubectl get pods -l ray.io/cluster=ray-efa -w
```

You should see 1 head pod on a general-purpose node and 2 worker pods on the 2 p5.48xlarge nodes.

### Step 7 — Submit the fine-tuning RayJob

The RayJob runs data-parallel LoRA fine-tuning of Qwen3-4B across all 16 H100 GPUs (16 workers × 1 GPU), using Ray Train's `TorchTrainer` + Hugging Face `Trainer` + PEFT.

```bash
kubectl apply -f manifests/finetune-rayjob.yaml

# Watch job status
kubectl get rayjob llama-lora-finetune -w

# Follow training logs
kubectl logs -l job-name=llama-lora-finetune --tail=100 -f
```

### Verify EFA is used for training

While the job runs, confirm NCCL selected the EFA/OFI transport (not TCP). `NCCL_DEBUG=INFO` prints the selected network:

```bash
# Grep a worker pod's logs for the NCCL transport line
kubectl logs -l ray.io/cluster=ray-efa,ray.io/node-type=worker --tail=500 \
  | grep -Ei "NET/OFI|Selected Provider|NET/Socket|EFA"
```

Key indicators:
- **`NET/OFI Selected provider is efa, fabric is efa-direct (found 8 nics)`** — NCCL is using EFA over all 8 interfaces. This is the goal (confirmed with the custom aws-ofi-nccl image).
- If you instead see **`NET/Socket`**, NCCL fell back to TCP — see Troubleshooting.

#### Captured EFA logs from an actual run

The following is real output from the fine-tuning RayJob on 2× p5.48xlarge (16 H100
GPUs). ANSI colors stripped; `pid`/`ip` prefixes shortened to `[node <ip>]`. Both
worker nodes (`192.168.184.241` and `192.168.185.113`) load the aws-ofi-nccl plugin
and select the **efa** provider. (This capture predates standardizing on the single
Ray 2.58.0 image; the aws-ofi-nccl plugin and EFA behavior are identical on the
current image.)

```text
[node 192.168.184.241] NCCL INFO NET/OFI Initializing aws-ofi-nccl 1.21.1
[node 192.168.184.241] NCCL INFO NET/OFI Plugin selected platform: AWS
[node 192.168.184.241] NCCL INFO NET/OFI Using Libfabric version 2.6
[node 192.168.184.241] NCCL INFO NET/OFI Using transport protocol RDMA (platform set)
[node 192.168.184.241] NCCL INFO NET/OFI Selected provider is efa, fabric is efa-direct (found 8 nics)
[node 192.168.184.241] NCCL INFO NET/OFI Support for DMA-BUF registrations: true
[node 192.168.184.241] NCCL INFO Using network Libfabric
[node 192.168.184.241] NCCL INFO ncclCommInitRank comm 0x... rank 0 nranks 16 cudaDev 0 busId 53000

[node 192.168.185.113] NCCL INFO NET/OFI Selected provider is efa, fabric is efa-direct (found 8 nics)   [repeated 15x across cluster]
[node 192.168.185.113] NCCL INFO NET/OFI Adding FI_EFA_FORK_SAFE=1 to environment
[node 192.168.185.113] NCCL INFO ncclCommInitRank comm 0x... rank 10 nranks 16 cudaDev 2 busId 75000 - Init COMPLETE   [repeated 14x across cluster]
```

What this proves:
- **`aws-ofi-nccl 1.21.1` + `Using network Libfabric`** — NCCL loaded the OFI plugin from the custom image (not the default socket transport). (The runtime-reported plugin version may differ from the `v1.13.2-aws` git tag used in Step 3.5 — aws-ofi-nccl's internal version string is numbered separately from its release tags.)
- **`Selected provider is efa, fabric is efa-direct (found 8 nics)`** on *both* nodes — the EFA/libfabric provider is active across all 8 EFA interfaces per node.
- **`nranks 16 ... Init COMPLETE`** — a single 16-GPU NCCL communicator spanning both nodes initialized successfully, so the cross-node all-reduce runs over EFA/SRD rather than TCP.

> For comparison, the **stock** `rayproject/ray:*-gpu` image (no aws-ofi-nccl) prints
> `libnccl-net.so: cannot open shared object file` and falls back to
> `NET/Socket` for the cross-node hop (e.g. `Channel .. : 0[0] -> 8[0] [send] via NET/Socket/0`).
> That is why the custom `Dockerfile.efa` image (Step 3.5) is required.

Confirm all 16 GPUs are in the Ray cluster and busy:

```bash
HEAD=$(kubectl get pod -l ray.io/cluster=ray-efa,ray.io/node-type=head -o jsonpath='{.items[0].metadata.name}')
kubectl exec $HEAD -- ray status | grep -E "GPU|node"
# Expect 16.0 GPU total across 2 worker nodes
```

When the job finishes, `kubectl get rayjob llama-lora-finetune` shows `SUCCEEDED` and the logs print `Final metrics:`.

### Step 8 — Tear down the fine-tuning resources

Before deploying inference (which reuses the same GPUs), remove the training resources:

```bash
kubectl delete -f manifests/finetune-rayjob.yaml
kubectl delete -f manifests/ray-cluster-efa.yaml
```

---

## Part B — Distributed inference

### Step 9 — Deploy the inference RayService

The RayService manages its own RayCluster and serves `Qwen/Qwen3-32B` across all 16 H100 GPUs with a 2D parallel layout: **`tensor_parallel_size=8`** (shard each layer across the 8 GPUs within a node, over NVLink) **+ `pipeline_parallel_size=2`** (split the 64 layers into 2 stages, one per node). Only the pipeline-stage activations cross the node boundary, and that cross-node hop runs over NCCL/EFA. This is the standard multi-node serving layout — it keeps the chatty per-layer all-reduce on NVLink and moves far less data over the network than cross-node TP would. (Qwen3-32B: 64 attention heads → TP divides 64; 64 layers → PP divides the layer count. Set `tensor_parallel_size: 8` with no PP to keep everything on a single node for comparison.)

> **Image note.** The RayService head and workers both use the
> `ray-efa:2.58.0-efa-vllm` image (Step 3.5), which bakes in Ray 2.58.0 + vLLM
> 0.26.0 + the aws-ofi-nccl plugin. There is **no** `runtime_env` pip install —
> installing vLLM at runtime fails because it would change the cluster's Ray
> version. The RayService `rayClusterConfig.rayVersion` is set to `2.58.0` to
> match.

```bash
kubectl apply -f manifests/inference-rayservice.yaml

# Wait for the service to become Running (first start downloads the model)
kubectl get rayservice llm-inference -w

# Follow serve/engine logs
kubectl logs -l ray.io/cluster -l app.kubernetes.io/name=kuberay --tail=100 -f 2>/dev/null \
  || kubectl logs -l ray.io/node-type=head --tail=100 -f
```

Wait until `kubectl get rayservice llm-inference` reports the service is `Running` and healthy.

### Test inference

```bash
# Port-forward the Ray Serve endpoint (head pod, :8000)
kubectl port-forward svc/llm-inference-serve-svc 8000:8000 &

# List models
curl -s http://localhost:8000/v1/models | python3 -m json.tool

# Chat completion
curl -s http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen/Qwen3-32B",
    "messages": [{"role":"user","content":"Explain Elastic Fabric Adapter in one sentence."}],
    "max_tokens": 128
  }' | python3 -m json.tool
```

### Verify tensor parallelism runs over EFA

```bash
# NCCL transport line from the engine startup
kubectl logs -l ray.io/node-type=worker --tail=800 \
  | grep -Ei "NET/OFI|Selected provider|tensor.parallel"
# Expect: NET/OFI Selected provider is efa, fabric is efa-direct (found 8 nics)
```

Because `pipeline_parallel_size=2` places the two pipeline stages on different nodes, vLLM must send stage activations across the node boundary — confirming cross-node communication over EFA. To keep everything on a single node (no cross-node traffic) for comparison, set `tensor_parallel_size: 8` and remove `pipeline_parallel_size`.

#### Captured inference results from an actual run

Verified end-to-end on 2× p5.48xlarge (16 H100). The RayService reached
`RUNNING` with both deployments `HEALTHY`:

```text
llm application: RUNNING
  LLMServer:Qwen--Qwen3-32B : HEALTHY
  OpenAiIngress             : HEALTHY
```

A live chat completion returned a real response. The `system_fingerprint` below
is from an earlier run that used `tensor_parallel_size=16` (hence `tp16`); the
manifest now uses `TP=8 × PP=2` for the same 16 GPUs, which serves identically
but is more network-efficient. It confirms vLLM 0.26.0 sharding across 16 GPUs:

```json
{
  "model": "Qwen/Qwen3-32B",
  "choices": [{ "message": { "role": "assistant",
      "content": "<think>\nOkay, the user is asking for a one-sentence definition of Elastic Fabric Adapter (EFA)... EFA is a network interface that allows EC2..." }}],
  "system_fingerprint": "vllm-0.26.0-tp16-3acf4511",
  "usage": { "prompt_tokens": 18, "completion_tokens": 60, "total_tokens": 78 }
}
```

And the vLLM engine's NCCL init confirms the cross-node tensor-parallel
all-reduce uses EFA (same OFI/libfabric path as training):

```text
NET/OFI Selected provider is efa, fabric is efa-direct (found 8 nics)   [repeated 15x across cluster]
Using network Libfabric
```

---

## Step 10 — Cleanup (do not skip)

```bash
# Delete whichever workload is running (frees the p5.48xlarge GPUs)
kubectl delete -f manifests/inference-rayservice.yaml --ignore-not-found
kubectl delete -f manifests/finetune-rayjob.yaml --ignore-not-found
kubectl delete -f manifests/ray-cluster-efa.yaml --ignore-not-found

# Uninstall the operators / plugins
helm uninstall kuberay-operator -n kuberay-system
helm uninstall efa -n kube-system

# Delete the custom Auto Mode resources
kubectl delete -f manifests/automode-nodepool-gpu.yaml --ignore-not-found
kubectl delete -f manifests/automode-nodeclass-efa.yaml --ignore-not-found
kubectl delete -f manifests/auto-ebs-sc.yaml --ignore-not-found

# Delete the secret
kubectl delete secret hf-token --ignore-not-found

# Delete the cluster (removes remaining Auto Mode nodes)
eksctl delete cluster --name ${CLUSTER_NAME} --region ${AWS_REGION}

# Delete the EFA security group (after the cluster/ENIs are gone)
aws ec2 delete-security-group --region ${AWS_REGION} --group-id ${EFA_SG} || true
```

Confirm in the EC2 console that no p5.48xlarge instances remain running, and cancel/verify the Capacity Block if you no longer need it (note: Capacity Block fees are non-refundable and instances auto-terminate at the block end).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Worker pod `Pending` forever | Capacity Block not active yet, or NodeClass/subnet/SG mismatch | `kubectl describe pod`; confirm the Capacity Block is `active`; confirm the gpu-efa NodePool is static (replicas set) and the subnet/SG tags resolve in the Capacity Block AZ |
| No p5 node ever provisions | NodePool/NodeClass not matching | `kubectl describe nodepool gpu-efa`; confirm the NodeClass `role` was substituted (no `REPLACE_WITH_...` left) and subnet/SG tags exist |
| Node launches but has no EFA / `Insufficient vpc.amazonaws.com/efa` | EFA device plugin not installed, or NodeClass didn't attach the EFA interface | Confirm `efa-aws-efa-k8s-device-plugin` DaemonSet is Ready; confirm `advancedNetworking.networkInterfaces` in the NodeClass and that the subnet is tagged in the single EFA AZ |
| NodeClass rejected / node fails to join | Wrong node IAM role or subnet/SG tags don't resolve | Re-run `kubectl get nodeclass default -o jsonpath='{.spec.role}'`; verify the `efa=true` SG tag and `kubernetes.io/role/efa=1` subnet tag exist in the VPC |
| Worker pod `Pending`, `Insufficient hugepages-2Mi` | Node hugepages not available | Auto Mode AL2023 accelerated AMIs pre-allocate 2Mi hugepages; confirm the pod requests match (`5120Mi`) and the node is a g6 EFA node |
| NCCL logs show `NET/Socket` instead of `NET/OFI ... efa` | EFA provider not found | Confirm `FI_PROVIDER=efa`, the `libnccl-ofi-tuner.so` path exists in the image, `LD_LIBRARY_PATH` includes `/opt/amazon/efa/lib`, and the pod actually got `vpc.amazonaws.com/efa: 1` |
| Ray head scheduled on a GPU node | Missing head `nodeSelector` | Confirm `nodeSelector: eks.amazonaws.com/nodepool: general-purpose` on the head group |
| GPU worker won't schedule | Missing toleration for the NodePool / GPU taints | Confirm the `ray.io/node-type=worker` and `nvidia.com/gpu` tolerations on the worker pods |
| Fine-tune job `401/403` pulling model | Gated model without a valid token | Recreate `hf-token` secret, or switch `--model` to an ungated model |
| Inference OOM on model load | model + KV cache + TP overhead exceeds H100 80 GB per shard | Lower `gpu_memory_utilization`, reduce `max_model_len`, or lower `tensor_parallel_size` |
| RayService stuck `not running` | Model still downloading, or Serve app import error | Check head/worker logs; increase readiness timeout; verify `import_path` |
| Both workloads scheduled at once | RayCluster + RayService both claim GPUs | Deploy **either** Part A **or** Part B — they share the same 16 GPUs |

---

## Files in this lab

```
ray-on-eks-efa/
├── README.md                        # this guide
├── Dockerfile.efa                   # Single Ray 2.58.0 image: EFA + aws-ofi-nccl + vLLM 0.26.0
│                                     #   -> tag: 2.58.0-efa-vllm (used by both training and inference)
└── manifests/
    ├── eksctl-cluster.yaml          # EKS Auto Mode cluster config
    ├── automode-nodeclass-efa.yaml  # Auto Mode NodeClass — attaches EFA interface at launch
    ├── automode-nodepool-gpu.yaml   # Auto Mode NodePool — static 2× p5.48xlarge (reserved/Capacity Block)
    ├── auto-ebs-sc.yaml             # default gp3 StorageClass for Auto Mode
    ├── ray-cluster-efa.yaml         # RayCluster with EFA, hugepages, /dev/shm, NCCL-over-EFA env
    ├── finetune-rayjob.yaml         # distributed LoRA fine-tuning RayJob (Ray Train, 16 GPUs)
    └── inference-rayservice.yaml    # Ray Serve LLM inference, TP=8 x PP=2 (16 GPU) over EFA
```

---

## References

- [Ray — Start Amazon EKS Cluster with GPUs for KubeRay](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/aws-eks-gpu-cluster.html)
- [Ray — Using GPUs on KubeRay](https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/gpu.html)
- [Ray Train — Hugging Face Transformers Guide](https://docs.ray.io/en/latest/train/getting-started-transformers.html)
- [Ray Serve — Serving LLMs](https://docs.ray.io/en/latest/serve/llm/serving-llms.html)
- [AWS — Manage EFA devices on Amazon EKS](https://docs.aws.amazon.com/eks/latest/userguide/device-management-efa.html) (Auto Mode + device plugin)
- [AWS — EKS Auto Mode](https://docs.aws.amazon.com/eks/latest/userguide/automode.html)
- [AWS — Deploy an accelerated workload on EKS Auto Mode](https://docs.aws.amazon.com/eks/latest/userguide/auto-accelerated.html)
- [AWS — Amazon EC2 G6 Instances](https://aws.amazon.com/ec2/instance-types/g6/)
- [KubeRay Documentation](https://docs.ray.io/en/latest/cluster/kubernetes/index.html)
