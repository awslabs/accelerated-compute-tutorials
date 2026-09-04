---

## title: AI Infra on AWS Guide — 사이트 구조 및 협업 가이드 date: 2026-09-02 author: Suji Lee

# AI Infra on AWS Guide — 사이트 구조 및 협업 가이드

## 1. 사이트 개요

| 항목 | 내용 |
| --- | --- |
| **사이트명** | AI Infra on AWS Guide |
| **서브타이틀** | 🇰🇷 AWS AI 인프라 실전 가이드 / 🇺🇸 Practical guides for AI infrastructure on AWS |
| **레포** | [awslabs/accelerated-compute-tutorials](https://github.com/awslabs/accelerated-compute-tutorials) |
| **배포** | GitHub Pages (MkDocs Material + GitHub Actions) |
| **라이선스** | MIT-0 |

---

## 2. 다국어 구조

### 기본 원리

```
docs/
├── ko/          ← 한국어 (기본 언어)
├── en/          ← 영어
├── images/      ← 공통 이미지
└── stylesheets/ ← 공통 CSS

```

- MkDocs i18n 플러그인 사용 (`docs_structure: folder`)
- **한국어가 기본(default)** — URL에 `/ko/`가 붙지 않음
- 영어는 URL에 `/en/`이 붙음
- 메뉴(nav)는 `mkdocs.yml`에서 **한글로 1개만 정의** → 영문은 `nav_translations`로 자동 번역

### Fallback 동작

현재 **fallback ON** 상태:

- `en/` 폴더에 해당 페이지가 없으면 → 한국어 페이지가 영문 사이트에 그대로 노출됨
- 장점: 영문 콘텐츠가 부족한 초기 단계에서 사이트가 비어보이지 않음
- 단점: 영문 사이트에 한국어 페이지가 섞여 보임

> **향후 계획**: 영문 콘텐츠가 충분히 쌓이면 `fallback_to_default: false`로 전환하여, 영문 페이지가 없는 항목은 영문 사이트에서 아예 노출되지 않도록 변경 예정.

---

## 3. 메뉴 구조 (nav)

### 협업 규칙

| 레벨 | 공통 강제 여부 | 설명 |
| --- | --- | --- |
| **1뎁스 (탭)** | ✅ 강제 | 양쪽 동일 — 합의 없이 추가/삭제/변경 불가 |
| **2뎁스 (서브섹션)** | ✅ 강제 | 양쪽 최소 `index.md` 필수 — 합의 필요 |
| **3뎁스 이하 (개별 페이지)** | 🔓 자율 | 각 언어별 독립 — 없으면 fallback |

### 탭 순서 및 2뎁스 구조

```
┌──────────┬──────────────┬────────────┬──────────────────┬──────────────┬───────────┐
│  AI Infra │ AWS Trainium │ NVIDIA GPU │ AI Infra 레시피  │ 교육 및 행사 │  최신소식  │
└──────────┴──────────────┴────────────┴──────────────────┴──────────────┴───────────┘

```

---

### 3.1 개요 (Overview)

| 2뎁스 | 설명 | 한글 | 영문 |
| --- | --- | --- | --- |
| 랜딩 페이지 | 사이트 소개 + 카드 바로가기 | ✅ | ✅ |
| 시작하기 | 사이트 사용법, 사전 준비 | ✅ | ✅ |

---

### 3.2 AI Infra

칩 종류와 무관한 **공통 인프라 설계·구축·운영 가이드**.

| 2뎁스 | 들어갈 콘텐츠 | 한글 | 영문 |
| --- | --- | --- | --- |
| AI 인프라 설계 | 인프라 의사결정 가이드, 가속기 선택 가이드, 리전 선택, 용량 계획 | ✅ | fallback |
| AI 인프라 구축/환경구성 | Docker/DLC, EFA 네트워킹, 스토리지 | ✅ | fallback |
| AI 인프라 운영 | 모니터링 & 스케일링, Capacity 모니터링 | ✅ | fallback |
| AI 인프라 Application | 서빙 프레임워크 비교, 배포 패턴 등 | ✅ | fallback |
| AI 인프라 Deep Dive | 스토리지·네트워킹 심화, 최적화, 벤치마크 & PoC | ✅ | fallback |
| 구매 옵션 | Capacity Blocks 가이드 등 | ✅ | fallback |

---

### 3.3 AWS Trainium

AWS 자체 설계 AI 칩(Trainium/NeuronCore) 전용 콘텐츠.

| 2뎁스 | 들어갈 콘텐츠 | 한글 | 영문 |
| --- | --- | --- | --- |
| 학습하기 | 학습경로, NDD Day1/Day2 핸즈온 랩 | ✅ | fallback |
| 추론 | vLLM on Neuron, vLLM + NxDI Classic (모델별 가이드) | ✅ | ✅ (일부) |
| 고객 사례 | 고객 적용 사례 | ✅ | fallback |

---

### 3.4 NVIDIA GPU

NVIDIA GPU 인스턴스(P5, G6e, G7e 등) 전용 콘텐츠.

| 2뎁스 | 들어갈 콘텐츠 | 한글 | 영문 |
| --- | --- | --- | --- |
| NVIDIA GPU 인스턴스 | 인스턴스 유형별 스펙·비교 가이드 | ✅ | fallback |

---

### 3.5 AI Infra 레시피 (AI Infra Recipes) 🆕

칩·플랫폼 무관한 **시나리오별 실전 핸즈온 레시피**. EKS, ParallelCluster, Trainium, NVIDIA GPU, Graviton 등 모두 포함 가능.

| 2뎁스 | 들어갈 콘텐츠 | 한글 | 영문 |
| --- | --- | --- | --- |
| AI Agents | OpenClaw on EKS, Crypto Trading Agent 등 | fallback | ✅ |
| Inference | Dynamo Disaggregated Inference 등 | fallback | ✅ |
| Training | Ray + EFA on EKS 분산학습 등 | fallback | ✅ |
| *(향후 확장)* | Graviton, ParallelCluster 등 | - | - |

---

### 3.6 교육 및 행사 (Training & Events)

AWS 주도 교육 프로그램(NDD, NFD, Immersion Day) 및 행사 일정.

| 2뎁스 | 들어갈 콘텐츠 | 한글 | 영문 |
| --- | --- | --- | --- |
| 교육 | Neuron Foundations Digest (NFD), Neuron Deep Dive (NDD) | ✅ | fallback |
| 행사 | 예정 행사 일정 | ✅ | fallback |
| 지난 행사 | 과거 행사 아카이브 | ✅ | fallback |

---

### 3.7 최신소식 (What's New)

| 2뎁스 | 들어갈 콘텐츠 | 한글 | 영문 |
| --- | --- | --- | --- |
| (단일 페이지) | Neuron SDK 릴리즈 노트, 주요 변경사항 | ✅ | fallback |

---

## 4. Branch Protection (예정)

현재 main 브랜치에 누구나 직접 push 가능한 상태입니다. 아래 설정을 적용할 예정:

| 설정 | 값 |
| --- | --- |
| Require pull request before merging | ✅ |
| Require approvals | 1명 (Suji) |
| Dismiss stale reviews | ✅ |

**작업 흐름:**

1. `main`에서 브랜치 생성 (예: `feat/add-new-guide`)
2. 작업 후 commit & push
3. GitHub에서 Pull Request 생성
4. 리뷰어 승인 후 Merge

---

## 5. 콘텐츠 추가 시 체크리스트

새 페이지를 추가할 때:

- [ ] `mkdocs.yml`의 `nav`에 경로 추가
- [ ] 해당 언어 폴더(`ko/` 또는 `en/`)에 `.md` 파일 생성
- [ ] 2뎁스 카테고리 신규 추가 시 → 양쪽 `index.md` 생성 + 팀 합의
- [ ] 이미지는 `docs/images/`에 공통 저장
- [ ] PR로 제출 → 리뷰 후 merge

---

## 6. 기술 스택

| 항목 | 사용 기술 |
| --- | --- |
| 정적 사이트 생성 | MkDocs |
| 테마 | Material for MkDocs (9.7.7+) |
| 다국어 | mkdocs-i18n 플러그인 |
| 다이어그램 | Mermaid (Material 번들) |
| 배포 | GitHub Actions → GitHub Pages |
| 로컬 실행 | `python3 -m venv .venv` → `pip install -r requirements.txt` → `mkdocs serve` |

