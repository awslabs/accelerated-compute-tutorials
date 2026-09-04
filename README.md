# AI Infra on AWS Guide

[![Deploy to GitHub Pages](https://github.com/awslabs/accelerated-compute-tutorials/actions/workflows/deploy.yml/badge.svg)](https://github.com/awslabs/accelerated-compute-tutorials/actions/workflows/deploy.yml)
[![License: MIT-0](https://img.shields.io/badge/License-MIT--0-yellow.svg)](https://opensource.org/licenses/MIT-0)

> Practical guides for running large-scale AI/ML workloads on AWS accelerated computing infrastructure

**🌐 Live Site**: [https://awslabs.github.io/accelerated-compute-tutorials/](https://awslabs.github.io/accelerated-compute-tutorials/)

## Ownership & Contribution

This site is owned by the **AWS AI Infra GTM Team**, managed by **Cheryl Abundo**.

| Role | Owner | Scope |
| --- | --- | --- |
| **Site Creator / Main Owner** | Suji Lee | Site architecture, layout, shared config (CSS, mkdocs.yml, overrides), nav structure |
| **Content Co-reviewer** | Wayne | Content review and PR approval |
| **Contributors** | Anyone | Contribute via Pull Request only — direct push to main is not allowed |

### Branch Protection

The `main` branch is protected. All changes must go through **PR → review → approval → merge**.

| Setting | Value |
| --- | --- |
| Require pull request before merging | ✅ |
| Require approvals | Suji and Wayne |
| Dismiss stale reviews | ✅ |

**Workflow:** branch off `main` → commit → push → open PR → Suji or Wayne reviews → merge.

## Bilingual Structure

The site supports **Korean (default)** and **English**.

```
docs/
├── ko/          ← Korean (default — no /ko/ in URL)
├── en/          ← English (/en/ in URL)
├── images/      ← Shared images
└── stylesheets/ ← Shared CSS
```

- Navigation is defined once in Korean (`mkdocs.yml` → `nav`), then auto-translated via `nav_translations`.
- **When adding a new menu item, you must register both Korean and English** in `mkdocs.yml`. Missing translations cause Korean text to appear on the English site.
- Fallback is ON — if an English page doesn't exist, the Korean page is shown on the English site.
- Translation requests are accepted via [GitHub Issues](https://github.com/awslabs/accelerated-compute-tutorials/issues). Translation PRs are also welcome.

## Site Structure

### Navigation Rules

| Level | Enforced? | Description |
| --- | --- | --- |
| **1st depth (tabs)** | ✅ Enforced | Must be identical across languages — requires team consensus to add/remove |
| **2nd depth (subsections)** | ✅ Enforced | Must have at least `index.md` on both sides — requires consensus |
| **3rd depth+ (pages)** | 🔓 Flexible | Independent per language — missing pages fall back |

### Tab Order & Content Guide

```
 AI Infra │ AWS Trainium │ NVIDIA GPU │ AI Infra Recipes │ Training & Events │ What's New
```

#### AI Infra

Chip-agnostic infrastructure guides — what you need to know regardless of Trainium or GPU.

| Subsection | What goes here? |
| --- | --- |
| **AI Infra Design** | Accelerator selection framework, infra decision guide, region selection — "what to choose" |
| **AI Infra Setup** | Docker/DLC, EFA networking, storage configuration — "how to set it up" |
| **AI Infra Operations** | vLLM monitoring, Grafana dashboards, KEDA autoscaling, Capacity monitoring — "what you need during operations" |
| **AI Infra Application** | Serving framework comparison, deployment patterns — "application-level design" |
| **AI Infra Deep Dive** | Storage/networking deep dives, optimization, benchmark & PoC methodology — "advanced topics" |
| **Purchase Options** | Capacity Blocks, On-Demand, Spot, Reserved — "how to procure accelerators" |

#### AWS Trainium

Trainium/NeuronCore-specific content — Neuron SDK, vLLM Neuron Plugin, NKI.

| Subsection | What goes here? |
| --- | --- |
| **Learning** | Learning path, NDD hands-on labs — "getting started with Trainium" |
| **Inference** | vLLM Neuron Plugin, per-model deployment guides — "serving models on Trainium" |
| **Case Studies** | Trainium adoption stories — "who uses it and how" |

#### NVIDIA GPU

NVIDIA GPU instance-specific content (P5, G6e, G7e, etc.).

| Subsection | What goes here? |
| --- | --- |
| **NVIDIA GPU Instances** | Instance specs comparison, workload-based selection — "which GPU instance to use" |

#### AI Infra Recipes

Chip/platform-agnostic **hands-on recipes** — step-by-step guides that work when you follow them. May include code, manifests, and Dockerfiles.

| Subsection | What goes here? |
| --- | --- |
| **AI Agents** | AI agent deployment on EKS — Agent Sandbox, gVisor/Kata isolation |
| **Inference** | Inference serving recipes — Disaggregated Inference, vLLM/TGI deployment |
| **Training** | Distributed training recipes — Ray+EFA, PyTorch distributed |
| **EKS** | EKS infrastructure recipes — GPU Operator, cluster configuration |
| **Profiling** | Performance profiling — Neuron Explorer, NKI kernel analysis |

> **AI Infra vs Recipes:** AI Infra = "guides for understanding and decision-making (reading)". Recipes = "step-by-step hands-on that works when you follow it (doing)".

#### Training & Events

AWS-led training programs and event schedules.

| Subsection | What goes here? |
| --- | --- |
| **Training Programs** | NFD, NDD — curriculum, prerequisites, lab guides |
| **Events** | Upcoming events, workshops, roadshows |
| **Past Events** | Event archives with recordings and materials |

#### What's New

Neuron SDK release notes and major updates. Chronologically updated.

## File Rules

### File Naming

| Type | Filename | Description |
| --- | --- | --- |
| Section landing page | `index.md` | Represents a folder. Do **NOT** use `README.md` — it breaks MkDocs URL routing. |
| Standalone page | `topic-name.md` | Single content page with no companion files (e.g. `vllm-on-neuron.md`) |
| Page with companion files | `folder/index.md` | When manifests, code, or Dockerfiles are included (e.g. `dynamo-disaggregated/index.md`) |

### Images

Some images contain language-specific text, so store images per language:

```
docs/
├── ko/images/    ← Korean images
├── en/images/    ← English images
└── images/       ← Shared images (language-neutral)
```

Organize subfolders freely, but keep them easy to identify (e.g. `ko/images/ndd/`, `en/images/recipes/dynamo/`).

## Contribution Checklist

Before submitting a PR:

- [ ] Added page path to `mkdocs.yml` → `nav`
- [ ] Registered English menu name in `mkdocs.yml` → `nav_translations`
- [ ] Created `.md` file in the correct language folder (`ko/` or `en/`)
- [ ] For new 2nd-depth categories → created `index.md` on both sides + team consensus
- [ ] Images stored in the correct language folder
- [ ] Submitted as PR → awaiting review

## Quick Start (Local Development)

```bash
git clone https://github.com/awslabs/accelerated-compute-tutorials.git
cd accelerated-compute-tutorials
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdocs serve
```

Open `http://127.0.0.1:8000` in your browser.

## Tech Stack

| Component | Technology |
| --- | --- |
| Static site generator | MkDocs |
| Theme | Material for MkDocs (9.7.7+) |
| i18n | mkdocs-static-i18n plugin |
| Diagrams | Mermaid (Material bundle) |
| Deployment | GitHub Actions → GitHub Pages |

## License

This project is licensed under the [MIT-0 License](LICENSE).
