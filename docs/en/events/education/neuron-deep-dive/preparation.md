# Preparation Checklist

> **Training:** AWS Neuron Deep Dive (Day 1 & Day 2)
> **Instance:** trn2.3xlarge (1 device, 4 logical cores, 96GB HBM)

## 1. System & Permission Requirements

### Common (Day 1 & Day 2)

| Category | Item | Detail |
| --- | --- | --- |
| **EC2 Quota** | trn2.3xlarge available | Service Quota: `Running On-Demand Trn Instances` ≥ 12 vCPU |
| **EBS** | Minimum 200GB gp3 | For model cache + NEFF compile cache |
| **Security Group** | SSH (22) | Participant access |
| | Port 8000 | vLLM API testing |
| | Port 3001 | Neuron Explorer Web UI |
| | Port 3002 | Neuron Explorer API Backend |
| | Port 8888 | Jupyter Notebook (optional) |
| **Outbound** | 443 (HTTPS) | HuggingFace Hub, PyPI, ECR access |
| **HuggingFace** | HF account + Access Token | Pre-approve gated models (Llama 3.1, etc.) |
| **IAM — ECR** | ① Public ECR | `public.ecr.aws/neuron/...` — no IAM required |
| | ② Private ECR (customer account) | `ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage`, `ecr:GetAuthorizationToken` |

### Day 1 Only

| Category | Item | Detail |
| --- | --- | --- |
| **OS/AMI** | Neuron DLAMI (Ubuntu 24.04) | ImageID:ami-098a48f87d9c99e69<br>Neuron driver + SDK + vLLM pre-installed |
| **Model Access** | `meta-llama/Llama-3.2-1B-Instruct` | [Pre-approve Meta license on HuggingFace](https://huggingface.co/meta-llama/Llama-3.2-1B-Instruct) |

### Day 2 Only

| Category | Item | Detail |
| --- | --- | --- |
| **OS/AMI** | Ubuntu 24.04 + Docker | DLC container-based labs |
| **Docker** | Installed + participant in docker group | `usermod -aG docker <user>` |
| **DLC Image** | PyTorch Native DLC (Private Beta) | Image URI shared separately. Pre-pull recommended (large size) |
| **Additional Disk** | EBS total 300GB+ recommended | NKI artifacts, NEFF cache, profile data accumulation |

## 2. Participant Prerequisites

### Before Day 1

| Item | Required/Recommended | Description |
| --- | --- | --- |
| Docker basics | Required | `pull`, `run`, `exec`, volume mount |
| Linux CLI | Required | SSH connection, basic commands (ls, cd, cat, grep) |
| ML/DL fundamentals | Required | Model, inference, parameters, tokens |
| AWS EC2 basics | Required | Instance types, SSH access, Security Groups |
| LLM concepts | Recommended | Transformer, attention, tokenizer |
| GPU-based inference experience | Recommended | vLLM or TGI experience is helpful |
| HuggingFace usage | Recommended | Model hub, config.json, tokenizer |

### Before Day 2

| Item | Required/Recommended | Description |
| --- | --- | --- |
| Day 1 completion | Required | Or equivalent Neuron fundamentals + vLLM serving experience |
| PyTorch experience | Required | `model.to()`, forward/backward, DataLoader |
| torch.compile concepts | Recommended | Graph tracing, FX Graph basics |
| GPU kernel concepts | Recommended | CUDA/Triton experience helps with NKI understanding |
| Profiler experience | Recommended | torch.profiler or Nsight experience |

!!! info "Learning Path"
    For self-study before Day 1 based on official documentation, see the [Learning Path](../../../aws-ai-chip/education/learning-path.md) page.

## 3. Summary Comparison

| | Day 1 | Day 2 |
| --- | --- | --- |
| **Theme** | Neuron Fundamentals & Inference Operations | PyTorch Native & NKI Optimization |
| **OS** | Neuron DLAMI | Ubuntu + Docker |
| **Environment** | DLAMI bare metal (vLLM built-in) | PyTorch Native DLC (Private Beta) |
| **Docker** | Not required | Required |
| **Lab** | vLLM deployment → monitoring → tuning | NKI kernel writing → benchmark → profiling |
