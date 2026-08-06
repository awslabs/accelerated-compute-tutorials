# Accelerated Compute Tutorials

[![Deploy to GitHub Pages](https://github.com/awslabs/accelerated-compute-tutorials/actions/workflows/deploy.yml/badge.svg)](https://github.com/awslabs/accelerated-compute-tutorials/actions/workflows/deploy.yml)
[![License: MIT-0](https://img.shields.io/badge/License-MIT--0-yellow.svg)](https://opensource.org/licenses/MIT-0)

> AWS 가속 컴퓨팅 인프라에서 대규모 AI/ML 워크로드를 실행하기 위한 실전 튜토리얼 모음

**🌐 Documentation Site**: [https://awslabs.github.io/accelerated-compute-tutorials/](https://awslabs.github.io/accelerated-compute-tutorials/)

---

## 📖 Overview

**Accelerated Compute Tutorials**는 AWS의 가속 컴퓨팅 인프라(Trainium, GPU)를 활용하여 대규모 AI/ML 워크로드를 효율적으로 실행하기 위한 실전 중심 튜토리얼을 제공합니다.

### 주요 카테고리

| 카테고리 | 설명 |
|---------|------|
| **추론 인프라** | vLLM, TGI 등을 활용한 대규모 모델 추론 배포 |
| **학습 인프라** | 분산 학습, PyTorch Native 학습 파이프라인 |
| **프로파일링 & 최적화** | Neuron Explorer, NKI 커널 최적화 |
| **에이전트 인프라** | AI 에이전트 실행 환경 구성 (향후 확장) |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- pip

### Local Development

```bash
# 레포지토리 클론
git clone https://github.com/awslabs/accelerated-compute-tutorials.git
cd accelerated-compute-tutorials

# 가상 환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 로컬 서버 실행
mkdocs serve
```

브라우저에서 `http://127.0.0.1:8000` 으로 접속하여 문서를 확인합니다.

### Build

```bash
mkdocs build
```

빌드된 정적 파일은 `site/` 디렉터리에 생성됩니다.

---

## 📁 Project Structure

```
accelerated-compute-tutorials/
├── .github/
│   └── workflows/
│       └── deploy.yml          # GitHub Pages 배포 워크플로우
├── docs/
│   ├── en/                     # English documentation
│   │   ├── index.md
│   │   ├── getting-started.md
│   │   ├── inference/
│   │   ├── training/
│   │   ├── profiling/
│   │   └── agents/
│   └── ko/                     # 한국어 문서 (기본)
│       ├── index.md
│       ├── getting-started.md
│       ├── inference/
│       ├── training/
│       ├── profiling/
│       └── agents/
├── overrides/                  # MkDocs Material theme overrides
├── mkdocs.yml                  # MkDocs 설정 파일
├── requirements.txt            # Python 의존성
├── CONTRIBUTING.md             # 기여 가이드
├── LICENSE                     # MIT-0 라이선스
└── README.md
```

---

## 🌍 Internationalization (i18n)

이 프로젝트는 **한국어(기본)** 와 **영어**를 지원합니다.

- 한국어: `/` (기본 경로)
- English: `/en/`

`mkdocs-static-i18n` 플러그인을 사용하며, 각 언어별 문서는 `docs/ko/`와 `docs/en/` 폴더에 분리되어 있습니다.

---

## 🤝 Contributing

기여를 환영합니다! 자세한 내용은 [CONTRIBUTING.md](CONTRIBUTING.md)를 참조하세요.

---

## 📄 License

This project is licensed under the [MIT-0 License](LICENSE).

---

## 🔗 Related Projects

- [AI on EKS](https://awslabs.github.io/ai-on-eks/) — Kubernetes 기반 AI/ML 워크로드 배포 가이드
- [AWS Neuron SDK](https://awsdocs-neuron.readthedocs-hosted.com/) — Trainium 개발 도구
- [Amazon EKS Blueprints](https://github.com/aws-ia/terraform-aws-eks-blueprints) — EKS 클러스터 프로비저닝
