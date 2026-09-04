# Neuron Deep Dive (NDD)

!!! note
    Availability of this training is subject to internal review. If interested, please contact your Account Manager (AM) or Solutions Architect (SA).

> **Format:** 3-Day modular (each Day can be taken independently)<br>
> **Duration:** 4 hours per Day<br>
> **Audience:** ML Engineers, Platform Engineers, AI Infra practitioners<br>
> **Level:** Beginner → Intermediate → Expert<br>
> **Prerequisites:** Basic understanding of machine learning and accelerators (GPUs, etc.)

## 🎯 Course Overview

A hands-on, production-oriented course covering Trainium hardware, deploying and optimizing LLM inference servers with the vLLM Neuron Plugin, and developing custom kernels with PyTorch Native and NKI.

| Day | Level | Theme | Audience |
| --- | --- | --- | --- |
| **Day 1** | Beginner | Neuron Fundamentals & Inference Operations | Engineers new to Neuron |
| **Day 2** | Intermediate | PyTorch Native & NKI Optimization | Day 1 graduates or equivalent |
| **Day 3** | Expert (Optional) | vLLM Model Onboarding & NAD | Day 1+2 graduates with deep model architecture understanding |

## 📅 Day 1 Agenda

**Neuron Fundamentals & Inference Operations** | 4 hours | Beginner

| Session | Topic | Duration | Content |
| --- | --- | --- | --- |
| 1 | Understanding the Neuron Platform | 50 min | Trainium2 hardware architecture, NeuronCore-v3, HBM, LNC configuration, Neuron SDK software stack |
| 2 | vLLM Neuron & Inference Operations | 50 min | vLLM Neuron Plugin architecture, performance tuning theory, new features (Disaggregated Inference, Speculative Decoding) |
| 3 | Monitoring & Profiling Theory | 40 min | neuron-top, Neuron Explorer, Perfetto profile analysis, Accuracy Debugging |
| 4 | Hands-on Lab | 75 min | Deploy vLLM server (Llama-3-8B), monitoring & profiling, performance tuning, new feature demo |
| - | Q&A | 5 min | |

## 📅 Day 2 Agenda

**PyTorch Native & NKI Optimization** | 4 hours | Intermediate

| Session | Topic | Duration | Content |
| --- | --- | --- | --- |
| 1 | PyTorch Native (TorchNeuron) Deep Dive | 60 min | torch.compile pipeline, data flow (HBM→SBUF→PSUM), Mixed Precision, distributed execution |
| 2 | NKI Fundamentals | 50 min | Neuron Kernel Interface overview, tile-based programming, 3 methods of PyTorch integration |
| 3 | Lab: PyTorch Native & NKI | 110 min | Eager mode inference, NKI kernel writing, PyTorch integration, profiling-based kernel optimization |
| - | Q&A | 5 min | |

## 📅 Day 3 Agenda

**vLLM Model Onboarding & NAD** | 4 hours | Expert (Optional)

| Session | Topic | Duration | Content |
| --- | --- | --- | --- |
| 1 | Model Onboarding Process | 50 min | 5-step onboarding, Plugin source structure, weight loading mapping, forward interface |
| 2 | Accuracy Debugging | 40 min | 3-level verification framework, 7-step debugging, CPU mode |
| 3 | Lab: Model Onboarding | 110 min | Existing model analysis, new model implementation, compile & smoke test, accuracy verification |
| 4 | NAD — AI-Powered Kernel Development | 20 min | NAD concepts, AI-assisted workflow demo |
| - | Q&A | 10 min | |

## ✅ Prerequisites

[:octicons-arrow-right-24: Preparation Checklist](preparation.md)

## 🔗 Related Courses

- [Neuron Foundations Digest (NFD)](../neuron-foundations/index.md) — Theory Introduction (1–2 hours)
