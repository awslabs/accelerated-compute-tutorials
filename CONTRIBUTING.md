# Contributing to Accelerated Compute Tutorials

기여해 주셔서 감사합니다! 🎉

이 문서는 프로젝트에 기여하기 위한 가이드라인을 설명합니다.

---

## 📋 How to Contribute

### 이슈 보고

버그, 오타, 개선 사항이 있다면 [GitHub Issues](https://github.com/awslabs/accelerated-compute-tutorials/issues)에 이슈를 생성해 주세요.

### Pull Request

1. 이 레포지토리를 **Fork** 합니다.
2. 새로운 브랜치를 생성합니다:
   ```bash
   git checkout -b feature/my-new-tutorial
   ```
3. 변경 사항을 커밋합니다:
   ```bash
   git commit -m "Add tutorial: vLLM deployment on Trainium"
   ```
4. Fork한 레포지토리에 Push 합니다:
   ```bash
   git push origin feature/my-new-tutorial
   ```
5. **Pull Request**를 생성합니다.

---

## 📝 Writing Guidelines

### 문서 구조

각 튜토리얼은 다음 구조를 따릅니다:

```markdown
---
title: 튜토리얼 제목
description: 간단한 설명
tags:
  - inference
  - neuron
---

# 튜토리얼 제목

## 개요

무엇을 배우는지, 왜 중요한지 설명합니다.

## 사전 요구사항

- 필요한 AWS 리소스
- 필요한 소프트웨어

## 단계별 가이드

### Step 1: ...
### Step 2: ...

## 정리 (Clean Up)

AWS 리소스 삭제 방법

## 참고 자료

관련 링크
```

### 다국어 문서

- **한국어** 문서는 `docs/ko/` 에 작성합니다.
- **영어** 문서는 `docs/en/` 에 작성합니다.
- 파일명은 동일하게 유지합니다 (예: `docs/ko/inference/vllm-on-neuron.md`, `docs/en/inference/vllm-on-neuron.md`).
- 한국어가 기본 언어이므로, 한국어 문서를 먼저 작성하는 것을 권장합니다.

### 코드 블록

- 모든 코드 블록에 언어를 명시합니다.
- 복사 가능하도록 `content.code.copy` 가 활성화되어 있습니다.
- 긴 명령어는 `\` 로 줄바꿈합니다.

```bash
kubectl apply -f deployment.yaml \
  --namespace inference \
  --context my-cluster
```

### Admonitions

중요한 정보는 admonition을 활용합니다:

```markdown
!!! warning "주의"
    이 튜토리얼은 비용이 발생할 수 있습니다.

!!! tip "팁"
    Spot 인스턴스를 활용하면 비용을 절감할 수 있습니다.

!!! info "참고"
    Neuron SDK 2.18 이상이 필요합니다.
```

---

## 🔧 Local Development

### 환경 설정

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 로컬 미리보기

```bash
mkdocs serve
```

`http://127.0.0.1:8000` 에서 실시간 미리보기가 가능합니다.

### 빌드 검증

```bash
mkdocs build --strict
```

`--strict` 플래그는 깨진 링크, 누락된 파일 등을 에러로 처리합니다.

---

## ✅ PR Checklist

Pull Request 제출 전 확인사항:

- [ ] `mkdocs build --strict` 가 에러 없이 통과
- [ ] 한국어/영어 문서 쌍이 모두 존재
- [ ] 코드 블록에 언어가 명시됨
- [ ] 이미지가 있는 경우 `docs/assets/` 에 저장
- [ ] 네비게이션(`mkdocs.yml`의 `nav`)에 새 페이지 추가

---

## 📄 License

이 프로젝트에 기여함으로써, 귀하의 기여가 [MIT-0 License](LICENSE)에 따라 라이선스됨에 동의합니다.

---

## 🙋 Questions?

궁금한 점이 있으면 [Discussions](https://github.com/awslabs/accelerated-compute-tutorials/discussions)에서 질문해 주세요.
