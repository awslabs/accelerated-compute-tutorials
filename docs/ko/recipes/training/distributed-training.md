---
title: Distributed Training
description: Configure large-scale distributed model training on AWS Trainium clusters
tags:
  - training
  - distributed
  - trainium
---

# Distributed Training

This tutorial guides you through distributed training of large language models on AWS Trainium clusters.

---

## Overview

AWS Trainium is a custom chip optimized for deep learning training, delivering the best cost-performance ratio.
The `neuronx-distributed` library enables easy implementation of data/tensor/pipeline parallel training.

---

## Prerequisites

- 2+ `trn1.32xlarge` instances
- EFA (Elastic Fabric Adapter) networking enabled
- Neuron SDK 2.18 or higher

---

## Step 1: Cluster Configuration

!!! note "Coming Soon"
    Detailed step-by-step guide will be added soon.

---

## References

- [Neuron Distributed Training Docs](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/frameworks/torch/torch-neuronx/programming-guide/training/neuronx-distributed/index.html)
- [AWS Trainium Instances](https://aws.amazon.com/ec2/instance-types/trn1/)
