# LoRA Fine-tuning with Megatron Bridge on KubeRay (single g6e.12xlarge) — Lab Guide

This hands-on lab fine-tunes **Qwen3-8B** with **LoRA** using **NVIDIA Megatron Bridge** (the Megatron-LM / Megatron Core training library with Hugging Face checkpoint support), orchestrated by **KubeRay** on **Amazon EKS Auto Mode**. Everything runs on a single **g6e.12xlarge** (4× NVIDIA L40S 48 GB): no EFA, no Capacity Block, and the GPU node exists only while the job runs.

Target region: **us-east-2** (any region that offers g6e.12xlarge works). GPUs: **1× g6e.12xlarge** = 4× L40S 48 GB, 48 vCPU, 384 GiB memory, on-demand.

> **Why Megatron Bridge and not plain Megatron-LM?** Megatron-LM's `pretrain_gpt.py` is built for pretraining from Megatron-format checkpoints. Megatron Bridge sits on top of the same Megatron Core engine and adds what fine-tuning needs: it loads a **Hugging Face checkpoint directly** (no separate conversion step), ships tested **SFT/LoRA recipes** per model, and **exports the LoRA adapter back to Hugging Face PEFT** format. It is what NVIDIA's NeMo Framework uses for Megatron-based training.

---

## How it fits together

```text
                 Amazon EKS Auto Mode (us-east-2)
┌───────────────────────────────────────────────────────────────────────┐
│  general-purpose NodePool (built-in)     gpu-g6e NodePool (this lab)  │
│  ┌───────────────────┐                   one g6e.12xlarge, on demand  │
│  │ KubeRay operator  │   creates   ┌──────────────────────────────────┐│
│  └─────────┬─────────┘ ──────────▶ │ Ray head pod (CPU only)          ││
│            │ RayJob                │  ├─ ray-job-submitter (sidecar)  ││
│            ▼                       │  └─ launch_bridge_finetune.py    ││
│   kubectl apply                    │            │ Ray actor            ││
│   finetune-rayjob.yaml             │            ▼                      ││
│                                    │ Ray GPU worker pod (4x L40S)     ││
│                                    │  1. download Qwen3-8B → /data/hf ││
│                                    │  2. torchrun x4 run_recipe.py    ││
│                                    │     --model qwen3_8b --mode lora ││
│                                    │  3. export adapter → /data/...   ││
│                                    │            │                     ││
│                                    │   EBS gp3 PVC /data (200Gi)      ││
│                                    └──────────────────────────────────┘│
└───────────────────────────────────────────────────────────────────────┘
```

| Piece | Role |
|-------|------|
| **RayJob** | Creates a short-lived RayCluster, runs the launcher, deletes the cluster afterwards |
| **`launch_bridge_finetune.py`** | Ray driver: puts one actor on the GPU worker, which downloads the model, runs `torchrun`, and exports the adapter |
| **Megatron Bridge `run_recipe.py`** | Loads the `qwen3_8b_peft_config` recipe, applies overrides, and trains with Megatron Core |
| **`gpu-g6e` NodeClass + NodePool** | Launches one g6e.12xlarge with a 300Gi root volume when the Ray pods are pending; removes it when they are gone |
| **`megatron-data` PVC** | Keeps the HF model cache, dataset cache, checkpoints, and adapters across runs |

Megatron Bridge does not need Ray to train; `torchrun` does the distributed launch. Ray (through KubeRay) provides the Kubernetes lifecycle: one `kubectl apply` gets you a cluster sized for the job, log streaming, cancellation, and automatic teardown. The same launcher pattern extends to more nodes later.

### Parallelism on L40S: why TP=1, DP=4

The four L40S GPUs in a g6e.12xlarge have **no NVLink**; they talk over PCIe. That decides the layout:

- **Tensor parallelism (TP)** splits every layer across GPUs and all-reduces activations twice per layer, every micro-batch. Over PCIe that traffic dominates the step time.
- **Data parallelism (DP)** gives every GPU a full copy of the model and only all-reduces **gradients**. With LoRA, the only gradients are the adapters: rank 8 on `linear_qkv` and `linear_proj` across Qwen3-8B's 36 layers is about **5.3M parameters (~21 MB in fp32)** per step, small even over PCIe.

A full bf16 copy of Qwen3-8B is about **16 GB**, which fits on a 48 GB L40S with room for activations at sequence length 2048, so this lab uses **TP=1, DP=4**. The recipe's global batch of 32 becomes micro-batch 1 × DP 4 × 8 gradient-accumulation steps.

---

## Prerequisites

- **AWS CLI**, **kubectl** (v1.30+), **eksctl** (v0.200.0+ for Auto Mode), **Helm** (v3+), and **Docker** with `buildx`.
- An AWS account with quota for **G and VT instances**: one g6e.12xlarge needs **48 vCPUs** of "Running On-Demand G and VT instances".
- A machine to build the image with **~100 GB free disk** (the NeMo base image is 18 GiB compressed). An amd64 EC2 instance builds fastest; building on Apple Silicon works through emulation but is slower.
- **No Hugging Face token required**: Qwen3-8B and the SQuAD dataset are public.

> **Cost.** You pay for one on-demand g6e.12xlarge **only while the RayJob runs**, plus ~10 minutes of idle time before Auto Mode removes the node, plus the EBS volumes and the EKS cluster. Check current rates in the [AWS Pricing Calculator](https://calculator.aws/). Run the cleanup step when you are done.

---

## Step 0 — Get the lab files

```bash
git clone https://github.com/awslabs/accelerated-compute-tutorials.git
cd accelerated-compute-tutorials/docs/en/ai-infra/orchestration/megatron-kuberay
```

All commands below run from this directory.

---

## Step 1 — Create the EKS Auto Mode cluster

```bash
export AWS_REGION="us-east-2"
export CLUSTER_NAME="megatron-ray-lab"

# Confirm g6e.12xlarge is offered in the region (lists the AZs):
aws ec2 describe-instance-type-offerings --region ${AWS_REGION} \
  --location-type availability-zone \
  --filters Name=instance-type,Values=g6e.12xlarge \
  --query 'InstanceTypeOfferings[*].Location' --output text

eksctl create cluster -f manifests/eksctl-cluster.yaml
```

If you change `CLUSTER_NAME` or `AWS_REGION`, change `metadata.name` / `metadata.region` in `manifests/eksctl-cluster.yaml` to match. Cluster creation takes about 15 minutes and configures `kubectl` when it finishes.

Capture the role of Auto Mode's built-in NodeClass; the GPU NodeClass reuses it:

```bash
export NODE_ROLE=$(kubectl get nodeclass default -o jsonpath='{.spec.role}')
echo "Auto Mode node role: ${NODE_ROLE}"
```

---

## Step 2 — Add the GPU NodeClass, NodePool, and storage

The built-in NodeClass gives nodes an **80Gi** root volume. The NeMo image is about 18 GiB compressed, and containerd keeps the compressed layers and the unpacked filesystem while it pulls, so this lab's NodeClass raises the root volume to **300Gi**. Everything else matches the built-in NodeClass: same node role (its EKS access entry already exists), eksctl's private subnets, and the cluster security group.

```bash
sed -i.bak \
  -e "s|REPLACE_WITH_NODE_ROLE|${NODE_ROLE}|" \
  -e "s|REPLACE_WITH_CLUSTER_NAME|${CLUSTER_NAME}|" \
  manifests/gpu-nodeclass.yaml

kubectl apply -f manifests/gpu-nodeclass.yaml
kubectl apply -f manifests/gpu-nodepool.yaml
kubectl apply -f manifests/storage.yaml

kubectl get nodeclass gpu-g6e     # READY should become True
kubectl get nodepool gpu-g6e
kubectl get pvc megatron-data     # Pending until the first pod mounts it (expected)
```

The `gpu-g6e` NodePool is a normal **dynamic** pool:

- It allows only `g6e.12xlarge`, on-demand.
- `limits: nvidia.com/gpu: "4"` caps it at **one** node.
- It taints nodes with `nvidia.com/gpu:NoSchedule`; only the Ray pods tolerate it.
- `consolidationPolicy: WhenEmpty` + `consolidateAfter: 10m` removes the node 10 minutes after the RayCluster is gone, and never while Ray pods are on it.

> If `kubectl get nodeclass gpu-g6e` does not become ready, check `kubectl describe nodeclass gpu-g6e`. The usual cause is a selector that matches nothing: confirm with `kubectl get nodeclass default -o yaml` which subnets and security groups the built-in NodeClass resolves, and adjust `subnetSelectorTerms` / `securityGroupSelectorTerms` to match.

---

## Step 3 — Build and push the image

`Dockerfile.bridge` starts from the **NVIDIA NeMo Framework container** (`nvcr.io/nvidia/nemo:26.08`), which already contains Megatron Bridge (in `/opt/Megatron-Bridge`), Megatron Core, Transformer Engine, PyTorch, NCCL, and CUDA 13. It adds only two things:

| Addition | Why |
|----------|-----|
| `ray[default]==2.56.1` | Ray head/worker + dashboard job API for KubeRay. Pinned to the Ray version in Megatron Bridge 0.6.x's own lockfile, so it matches what the NeMo venv was resolved against |
| `wget` | Used by the KubeRay readiness/liveness probes |

The build also **fails early** if the base image does not have Megatron Bridge 0.6 or newer, the `qwen3_8b_peft_config` recipe, `run_recipe.py`, and the adapter exporter. So a changed base image shows up at build time, not halfway through a GPU job.

```bash
export ECR="$(aws sts get-caller-identity --query Account --output text).dkr.ecr.${AWS_REGION}.amazonaws.com"
export IMAGE="${ECR}/megatron-bridge-ray:nemo26.08-ray2.56.1"

aws ecr create-repository --region ${AWS_REGION} --repository-name megatron-bridge-ray || true
aws ecr get-login-password --region ${AWS_REGION} \
  | docker login --username AWS --password-stdin ${ECR}

docker buildx build --platform linux/amd64 -f Dockerfile.bridge -t ${IMAGE} --push .
```

The build prints a line like `megatron-bridge 0.6.x | ray 2.56.1`. Keep it: it tells you exactly which Megatron Bridge version your job will run.

> **No EFA layer.** Unlike the [Ray + EFA lab](../ray-on-eks-efa/index.md), this image has no EFA installer or aws-ofi-nccl plugin. With one node, every NCCL collective stays inside the machine (PCIe or shared memory), so there is no network transport to configure.

---

## Step 4 — Install the KubeRay operator

```bash
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm repo update

helm install kuberay-operator kuberay/kuberay-operator \
  --version 1.7.0 \
  --namespace kuberay-system --create-namespace

kubectl get pods -n kuberay-system   # kuberay-operator-... 1/1 Running
```

The operator runs on Auto Mode's general-purpose nodes.

---

## Step 5 — Submit the fine-tuning RayJob

Load the launcher into a ConfigMap, point the RayJob at your image, and apply it:

```bash
kubectl create configmap megatron-launcher \
  --from-file=launch_bridge_finetune.py=scripts/launch_bridge_finetune.py

sed -i.bak "s|REPLACE_WITH_IMAGE|${IMAGE}|g" manifests/finetune-rayjob.yaml

kubectl apply -f manifests/finetune-rayjob.yaml
```

What `finetune-rayjob.yaml` sets up:

- **Head pod** (4 CPU, 16 GiB, no GPUs) and **one GPU worker pod** (40 CPU, 320 GiB, `nvidia.com/gpu: 4`), both on the `gpu-g6e` NodePool, so Auto Mode launches a single g6e.12xlarge and pulls the image once.
- **`submissionMode: SidecarMode`**: KubeRay runs `ray job submit` as a sidecar container inside the head pod. With the default `K8sJobMode`, the submitter is a separate pod that uses the head image. It would land on a small general-purpose node and pull 18 GiB there.
- **Worker environment**:
    - `HF_HOME=/data/hf` and `NEMO_HOME=/data/nemo` put the model and dataset caches on the PVC.
    - `NCCL_NET_PLUGIN=none` overrides the NeMo image's InfiniBand-oriented default, because one node has no network fabric to use.
    - `NCCL_DEBUG=INFO` prints the transport NCCL picks, for the first run.
- **Lifecycle**:
    - `shutdownAfterJobFinishes: true` with `ttlSecondsAfterFinished: 600` deletes the RayCluster 10 minutes after the job ends.
    - `backoffLimit: 0` stops a failed job from silently re-running.
    - `activeDeadlineSeconds: 10800` is a 3-hour safety net.

The entrypoint runs the launcher with the recipe defaults:

```text
python /opt/launcher/launch_bridge_finetune.py
  --model qwen3_8b --gpus 4 --cpus 32 --tp 1
  --max-steps 100 --global-batch-size 32 --micro-batch-size 1
  --save-dir /data/checkpoints/qwen3-8b-lora
  --export-dir /data/adapters/qwen3-8b-lora
```

Inside the GPU worker, the launcher's Ray actor:

1. Downloads `Qwen/Qwen3-8B` at the revision the Megatron Bridge recipe pins, into `/data/hf`. This is skipped on later runs because the cache is on the PVC.
2. Runs Megatron Bridge on all four GPUs:
    ```text
    torchrun --standalone --nproc_per_node 4 /opt/Megatron-Bridge/scripts/training/run_recipe.py \
      --model qwen3_8b --mode lora \
      --pretrained_checkpoint /data/hf/hub/models--Qwen--Qwen3-8B/snapshots/<rev> \
      --save_dir /data/checkpoints/qwen3-8b-lora -tp 1 -ms 100 -gb 32 -mb 1
    ```
    `--model qwen3_8b --mode lora` selects the `qwen3_8b_peft_config` recipe. Its defaults are LoRA rank 8 / alpha 16 on `linear_qkv` and `linear_proj`, sequence length 2048, packed **SQuAD** downloaded from the Hugging Face Hub, bf16, and the distributed optimizer. Because `--pretrained_checkpoint` points at a Hugging Face directory (`config.json` + `*.safetensors`), Megatron Bridge converts the weights to Megatron format in memory at startup.
3. Exports the LoRA adapter with Megatron Bridge's `examples/conversion/adapter/export_adapter.py` to `/data/adapters/qwen3-8b-lora` (`adapter_config.json` + `adapter_model.safetensors`).

    The exporter has to be given one checkpoint **iteration** directory, e.g. `/data/checkpoints/qwen3-8b-lora/iter_0000100`. In Megatron Bridge 0.6.x it rejects the parent `--save-dir` with `... is not a distributed checkpoint`, even though its docstring says the parent works. So the launcher passes the newest complete `iter_*` directory: one that contains the distributed-checkpoint metadata file. A save that was cut off halfway is skipped.

---

## Step 6 — Watch the job

```bash
# Job status: Initializing -> Running -> Complete (deploymentStatus) / SUCCEEDED (jobStatus)
kubectl get rayjob qwen3-lora -w
```

In a second terminal, watch the GPU node come up. The first run takes longest because of the node launch, the 18 GiB image pull, and the ~16 GB model download:

```bash
kubectl get nodeclaims -w                  # one g6e.12xlarge from the gpu-g6e pool
export RC=$(kubectl get rayjob qwen3-lora -o jsonpath='{.status.rayClusterName}')
kubectl get pods -l ray.io/cluster=${RC} -o wide -w
```

Follow the job output. In SidecarMode it streams from the `ray-job-submitter` container in the head pod:

```bash
export HEAD=$(kubectl get pod -l ray.io/cluster=${RC},ray.io/node-type=head -o jsonpath='{.items[0].metadata.name}')
kubectl logs -f ${HEAD} -c ray-job-submitter
```

You should see, in order:

- the launcher's `[launcher] qwen3_8b: 4 GPUs | TP=1 DP=4 | global batch 32 = micro 1 x DP 4 x 8 accumulation steps` line
- the model download (`[launcher] model ready at /data/hf/hub/models--Qwen--Qwen3-8B/snapshots/...`)
- the full `torchrun ... run_recipe.py ...` command
- Megatron Bridge loading the recipe, preparing and packing the SQuAD dataset (first run only), and loading the HF weights
- Megatron training-log lines with `iteration N/100`, `lm loss`, and `elapsed time per iteration`, plus validation loss every 30 iterations
- `[launcher] training exited with 0`, `[launcher] exporting adapter from /data/checkpoints/qwen3-8b-lora/iter_0000100`, the export output, and `[launcher] adapter export exited with 0; adapter in /data/adapters/qwen3-8b-lora`

---

## Step 7 — Verify

While the job runs, or within 10 minutes after it ends (before the RayCluster is deleted):

**GPUs and driver.** The NeMo 26.08 image uses CUDA 13, which needs NVIDIA driver **580 or newer** on the host:

```bash
export WORKER=$(kubectl get pod -l ray.io/cluster=${RC},ray.io/node-type=worker -o jsonpath='{.items[0].metadata.name}')
kubectl exec ${WORKER} -- nvidia-smi --query-gpu=index,name,memory.used,memory.total,driver_version --format=csv
# Expect 4 rows of "NVIDIA L40S", driver_version 580.x or newer
```

**Ray sees the GPUs:**

```bash
kubectl exec ${HEAD} -c ray-head -- ray status | grep -E "GPU|CPU"
# 4.0 GPU total; 4.0/4.0 used while training
```

**NCCL transport (single node, no network):**

```bash
kubectl logs ${HEAD} -c ray-job-submitter | grep -E "NCCL INFO (Channel|Using network|ncclCommInitRank)" | head -20
```

Each rank should report `nranks 4`, and the channels should go `via P2P/...` or `via SHM/...`. Which one depends on whether the instance exposes PCIe peer-to-peer between the GPUs. Neither uses the network. NCCL may also print `Using network Socket`: that is the transport it would use between nodes, and a single-node job has no such traffic.

**The adapter was written:**

```bash
kubectl exec ${WORKER} -- ls -la /data/adapters/qwen3-8b-lora /data/checkpoints/qwen3-8b-lora
# adapter_config.json  adapter_model.safetensors   |   iter_0000100/ ...
```

---

## Step 8 — Use the adapter

Copy the adapter out before the RayCluster is deleted (`ttlSecondsAfterFinished: 600`). Afterwards it is still on the PVC, and you can mount the PVC in any pod to reach it.

```bash
kubectl cp ${WORKER}:/data/adapters/qwen3-8b-lora ./qwen3-8b-lora
```

It is a standard Hugging Face PEFT adapter:

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3-8B", dtype="auto", device_map="auto")
model = PeftModel.from_pretrained(base, "./qwen3-8b-lora")
tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-8B")
```

vLLM can also serve it with `--enable-lora --lora-modules qwen3-lora=./qwen3-8b-lora`.

---

## Customizing the run

Anything after the launcher's own flags is passed straight to `run_recipe.py`. That includes its common flags and any `KEY=VALUE` override of the recipe's `ConfigContainer`; trailing overrides win. Edit the `entrypoint` in `finetune-rayjob.yaml`, then delete and re-apply the RayJob.

| Goal | Add to the entrypoint |
|------|----------------------|
| Train longer | `--max-steps 500` (also consider `scheduler.lr_decay_iters=500`) |
| Different learning rate | `--lr 2e-4` |
| Larger LoRA rank | `peft.dim=16 peft.alpha=32` |
| Different built-in dataset | `--dataset gsm8k` (others in Megatron Bridge 0.6.x: `squad`, `tulu3`, `openmathinstruct2`, `local-jsonl`) |
| Save checkpoints more often | `--save_interval 50` |

Each run starts fresh from the Hugging Face weights. Resuming would need `--load_dir`, which the launcher does not set. So give each run its own `--save-dir` and `--export-dir`, so checkpoints from different runs do not mix:

```bash
kubectl delete rayjob qwen3-lora
# edit the entrypoint (new --save-dir / --export-dir, overrides), then:
kubectl apply -f manifests/finetune-rayjob.yaml
```

To preview the exact commands the launcher will run without a cluster or GPUs:

```bash
python3 scripts/launch_bridge_finetune.py --dry-run --max-steps 500 --lr 2e-4
```

---

## Step 9 — Cleanup (do not skip)

```bash
kubectl delete rayjob qwen3-lora --ignore-not-found
kubectl delete configmap megatron-launcher --ignore-not-found
kubectl delete secret hf-token --ignore-not-found

helm uninstall kuberay-operator -n kuberay-system

# Deleting the PVC deletes the EBS volume with the model cache, checkpoints and adapters.
kubectl delete -f manifests/storage.yaml --ignore-not-found
kubectl delete -f manifests/gpu-nodepool.yaml --ignore-not-found
kubectl delete -f manifests/gpu-nodeclass.yaml --ignore-not-found

eksctl delete cluster --name ${CLUSTER_NAME} --region ${AWS_REGION}

# Optional: remove the image repository
aws ecr delete-repository --region ${AWS_REGION} --repository-name megatron-bridge-ray --force
```

Confirm in the EC2 console that no g6e.12xlarge instance and no `megatron-data` EBS volume remain.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Pods `Pending`, no NodeClaim created | NodePool/NodeClass not ready, or GPU quota | `kubectl describe nodepool gpu-g6e`, `kubectl describe nodeclass gpu-g6e`; check for leftover `REPLACE_WITH_...`; check the "Running On-Demand G and VT instances" quota (needs 48 vCPU) |
| NodeClaim created but never `Ready` | Instance can't join (subnet/SG selectors), or no g6e capacity in the chosen AZ | `kubectl describe nodeclaim`; compare the NodeClass selectors with `kubectl get nodeclass default -o yaml` |
| Pod stuck in `ContainerCreating` for a long time | 18 GiB image pull on first launch | `kubectl describe pod` shows `Pulling image`; wait. Later runs on the same node are faster, but a new node pulls again |
| Pod evicted, `ephemeral-storage` / `DiskPressure` | Root volume too small for the image | Confirm the NodeClass `ephemeralStorage.size` is `300Gi` and the pod is on a `gpu-g6e` node |
| Image build fails at the version check | Base image changed (Megatron Bridge < 0.6, or a different Ray) | Pin a NeMo tag that has Megatron Bridge 0.6.x, or adjust `RAY_VERSION` and `rayVersion` together |
| `CUDA driver version is insufficient` | Host driver older than CUDA 13 needs | Check `nvidia-smi` on the worker (Step 7); Auto Mode GPU nodes need driver 580+ for NeMo 26.x images |
| Launcher: `no worker with 4 GPUs after 1800s` | Worker pod never started | `kubectl get pods -l ray.io/cluster=${RC}`; `kubectl describe pod` on the worker |
| Training succeeds, then export fails: `CheckpointingException: /data/checkpoints/... is not a distributed checkpoint` | The exporter was given the run directory instead of an `iter_*` directory (launcher versions before this fix) | Use the current `launch_bridge_finetune.py`, which passes the newest complete `iter_*` directory, and recreate the `megatron-launcher` ConfigMap |
| `[launcher] error: no complete iter_* checkpoint in ...` | Training ended without a full checkpoint (for example, `--save_interval` larger than `--max-steps`, or the save was interrupted) | Check `ls /data/checkpoints/<run>/` on the worker; make sure a save happens at or before the last step |
| `CUDA out of memory` | Bigger micro-batch or model than the defaults | Keep `--micro-batch-size 1`; add `model.recompute_granularity=selective` to recompute activations in the backward pass |
| Job fails downloading model or dataset | No outbound internet from the nodes, or Hub rate limiting | Nodes need egress to `huggingface.co`; set an `hf-token` secret to avoid anonymous rate limits: `kubectl create secret generic hf-token --from-literal=HF_TOKEN=hf_...` |
| `kubectl logs ... -c ray-job-submitter` is empty or exits early | Submitter still waiting for the dashboard, or the log stream dropped | Re-run the command; `kubectl exec ${HEAD} -c ray-head -- ray job list` shows the job state |
| RayJob deleted, but the node is still up | Node removed only after `consolidateAfter: 10m` with no pods | Wait 10 minutes; `kubectl get nodeclaims` |

---

## Files in this lab

```text
megatron-kuberay/
├── index.md                          # this guide
├── Dockerfile.bridge                 # NeMo 26.08 (Megatron Bridge) + ray[default] 2.56.1 + wget
├── scripts/
│   └── launch_bridge_finetune.py     # Ray driver: download model -> torchrun run_recipe.py -> export adapter
└── manifests/
    ├── eksctl-cluster.yaml           # EKS Auto Mode cluster
    ├── gpu-nodeclass.yaml            # Auto Mode NodeClass: built-in settings + 300Gi root volume
    ├── gpu-nodepool.yaml             # Auto Mode NodePool: one on-demand g6e.12xlarge, scales to zero
    ├── storage.yaml                  # gp3 StorageClass + 200Gi PVC mounted at /data
    └── finetune-rayjob.yaml          # RayJob: CPU head (SidecarMode submitter) + 4-GPU worker
```

---

## References

- [Megatron Bridge documentation](https://docs.nvidia.com/nemo/megatron-bridge/latest/) and [GitHub](https://github.com/NVIDIA-NeMo/Megatron-Bridge)
- [Megatron Bridge — Using Recipes](https://docs.nvidia.com/nemo/megatron-bridge/latest/recipe-usage.html)
- [Megatron Bridge — Training Entry Points](https://docs.nvidia.com/nemo/megatron-bridge/latest/training/entry-points.html)
- [NeMo Framework container (NGC)](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/nemo)
- [KubeRay — RayJob quickstart](https://docs.ray.io/en/latest/cluster/kubernetes/getting-started/rayjob-quick-start.html)
- [AWS — Create a Node Class for EKS Auto Mode](https://docs.aws.amazon.com/eks/latest/userguide/create-node-class.html)
- [AWS — Deploy an accelerated workload on EKS Auto Mode](https://docs.aws.amazon.com/eks/latest/userguide/auto-accelerated.html)
- [AWS — Amazon EC2 G6e instances](https://aws.amazon.com/ec2/instance-types/g6e/)
- Related lab: [Ray + EFA on EKS](../ray-on-eks-efa/index.md) (multi-node, 2× p5.48xlarge with EFA)
