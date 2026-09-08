# AI Infra on AWS Guide

[![Deploy to GitHub Pages](https://github.com/awslabs/accelerated-compute-tutorials/actions/workflows/deploy.yml/badge.svg)](https://github.com/awslabs/accelerated-compute-tutorials/actions/workflows/deploy.yml)
[![License: MIT-0](https://img.shields.io/badge/License-MIT--0-yellow.svg)](https://opensource.org/licenses/MIT-0)

> Practical guides for running large-scale AI/ML workloads on AWS accelerated computing infrastructure

**🌐 Live Site**: [https://awslabs.github.io/accelerated-compute-tutorials/](https://awslabs.github.io/accelerated-compute-tutorials/)

## Ownership & Contribution

This site is owned by the **AWS AI Infra GTM Team** (Manager: **Cheryl Abundo**).

| Role | Owner | Scope |
| --- | --- | --- |
| **Site Creator / Main Owner** | Suji Lee | Site architecture, layout, shared config (CSS, mkdocs.yml, overrides), nav structure |
| **Content Co-reviewer** | Wayne | Content review and PR approval |
| **Contributors** | AI Infra GTM Team members | Contribute via Pull Request only — direct push to main is not allowed |

### Branch Protection

The `main` branch is protected. All changes must go through **PR → review → approval → merge**.

| Setting | Value |
| --- | --- |
| Require pull request before merging | ✅ |
| Require approvals | Suji and Wayne |
| Dismiss stale reviews | ✅ |

**Workflow:** branch off `main` → commit → push → open PR → Suji or Wayne reviews → merge.

## Bilingual Structure

The site carries the **full page set in both languages**. Korean is currently the
default locale; English is planned to take over (see [Roadmap](#roadmap-english-as-default)).

```
docs/
├── ko/          ← Korean (default locale — no /ko/ in URL)
├── en/          ← English (/en/ in URL)
├── images/      ← Images (see Images below)
└── stylesheets/ ← Shared CSS
```

### Navigation

`nav` in `mkdocs.yml` is the **single source of truth for both locales**. There is one
physical tree, so the two languages cannot drift apart.

- Labels in `nav` are written in **English**.
- Korean labels live in `plugins → i18n → languages[ko] → nav_translations`.
- **When adding a page:** add it to `nav` with an English label, then add a Korean label
  to `nav_translations` if it needs translating. Labels that are identical in both
  languages (e.g. `AWS Trainium`) need no entry.
- A missing `nav_translations` entry makes the **English label appear on the Korean site**.

### Fallback

Fallback is ON, and it is **unidirectional — it always falls back to the default locale**.
Today the default is Korean, so a missing English page serves the Korean content at its
`/en/` URL. The reverse does not happen.

This single fact drives the whole architecture: **the default locale must be the complete
language.** It is why English cannot become the default until every page is translated.

### Language Entry Routing

Visitors are sent to the build matching their browser language — Korean browsers to
Korean, everyone else to **English**. The script lives in `overrides/main.html` and runs
in `<head>`, so the wrong language never flashes on screen.

Picking a language from the header switcher stores that choice in `localStorage`
(`docs-preferred-lang`) and **always wins** over automatic routing from then on. If you
are testing and seem stuck in one language, clear that key.

### Roadmap: English as Default

Search engines are pointed at English (`hreflang="x-default"` → `/en/`). Making English
the actual default is a **2-line config change**, but it is blocked until translation is
complete — because of the unidirectional fallback above, flipping it early breaks every
untranslated page instead of falling back.

Translation is therefore the highest-value contribution right now. Requests go to
[GitHub Issues](https://github.com/awslabs/accelerated-compute-tutorials/issues);
translation PRs are welcome.

## Site Structure

### Navigation Rules

Because `nav` is one shared tree, **the structure is identical across languages at every
depth** — it is not possible for one language to have a menu item the other lacks. What
differs is only whether a given page has been translated yet.

| Level | Change process |
| --- | --- |
| **1st depth (tabs)** | Requires team consensus to add or remove |
| **2nd depth (subsections)** | Requires consensus; needs an `index.md` in `ko/` at minimum |
| **3rd depth+ (pages)** | Add freely via PR — untranslated pages fall back |

Only the default locale (`ko/`) has to contain the file; the other locale falls back until
it is translated. Once English becomes the default, every page will need to exist in `en/`
— which is exactly what makes the flip a translation problem rather than a config one.

### Tab Order & Content Guide

```
 Overview │ AI Infra │ AWS Trainium │ NVIDIA GPU │ AI Infra Recipes │ Training & Events │ What's New
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

### Excluded from the Site

Files matching these patterns are dropped from the build, the sitemap and search
(`exclude_docs` in `mkdocs.yml`):

| Pattern | Purpose |
| --- | --- |
| `_*.md` | Internal notes, drafts and templates — e.g. `_page-template.md`, `_backlog.md` |
| `trading-agent/` | Lab container sources referenced only from a Dockerfile `COPY` line |

**Prefix a filename with `_` to keep a work-in-progress page out of the published site.**
Rename it once it is ready.

### Images

Store images under `docs/images/`, split by language, because some contain
language-specific text:

```
docs/images/
├── ko/       ← Korean images
├── en/       ← English images
└── *         ← Shared images (language-neutral)
```

Organize subfolders freely but keep them identifiable (e.g. `images/ko/ndd-day1-lab/`,
`images/en/recipes/dynamo/`). Reference them with a relative path from your page —
for example `![...](../../../images/ko/ndd-day1-lab/lab0-opt.png)`.

> **Note:** `docs/images/en/` does not exist yet — create it with the first English image.
> A few older images still sit next to their page instead of under `docs/images/`; new
> contributions should follow the layout above.

## Contribution Checklist

Before submitting a PR:

- [ ] Added page path to `mkdocs.yml` → `nav`, with an **English** label
- [ ] Registered the **Korean** label in `mkdocs.yml` → `languages[ko]` → `nav_translations`
      (skip if the label is the same in both languages)
- [ ] Created `.md` file in the correct language folder (`ko/` or `en/`)
- [ ] For new 2nd-depth categories → created `index.md` on both sides + team consensus
- [ ] Images stored under `docs/images/<lang>/`
- [ ] Did not add Korean text to `site_name` / `site_description` / `copyright` /
      `theme` — these are English-only (see [Localization Policy](#localization-policy))
- [ ] `mkdocs build --strict` passes locally
- [ ] Submitted as PR → awaiting review

## Localization Policy

| What | Language | Where |
| --- | --- | --- |
| Page content | Per locale | `docs/ko/`, `docs/en/` |
| Menu labels | Per locale | `nav` (English) + `nav_translations` (Korean) |
| Branding copy — announce banner, site subtitle | Per locale | `overrides/main.html`, branched on `config.theme.language` at build time |
| Site metadata — `site_name`, `site_description`, `copyright` | **English only** | `mkdocs.yml` |
| Theme UI — search, TOC, prev/next | Automatic | Material, via `theme.language` |
| Our own UI strings — nav collapse, draft badge, palette toggle | **English only** | `overrides/main.html`, `mkdocs.yml` |

Two rules worth knowing before you edit:

- **Do not override `theme.language`.** The i18n plugin sets it per locale, and Material
  derives `<html lang>` from it. Forcing it to one value breaks screen readers and sends
  the wrong signal to search engines.
- **When changing branding copy, update both branches** of the Jinja conditional in
  `overrides/main.html` — otherwise one language keeps the old text.

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

Before opening a PR, verify the build the same way CI does:

```bash
mkdocs build --strict
```

## Tech Stack

Versions below are the minimums declared in `requirements.txt`, which is the source of
truth — update it rather than this table when bumping a dependency.

| Component | Technology | Minimum |
| --- | --- | --- |
| Static site generator | MkDocs | `>=1.6.0,<2.0.0` |
| Theme | Material for MkDocs | `>=9.5.0` |
| i18n | mkdocs-static-i18n | `>=1.2.0` |
| Markdown extensions | pymdown-extensions | `>=10.0` |
| Diagrams | Mermaid (Material bundle) | — |
| Deployment | GitHub Actions → GitHub Pages | — |

## License

This project is licensed under the [MIT-0 License](LICENSE).
