# 랜딩 페이지 설계 권고안

> 작성: 2026-09-29 | 대상: `docs/en/index.md`, `docs/ko/index.md` 및 1단계 섹션 랜딩
> 이 폴더(`docs-notes/`)는 `docs/` 밖에 있으므로 사이트 빌드에 포함되지 않습니다.

## 결론

**옵션 2(구조 안의 격상된 홈 페이지)를 지금 적용하고, 옵션 1(전용 스플래시 페이지)은 영어 메인 승격(STAGE 4) 시점에 별도 작업으로 검토합니다.**

현재 `docs/en/index.md` / `docs/ko/index.md` 는 옵션 2로 구현되어 있습니다.

## 참고: AI on EKS 는 어떻게 하고 있나

- AI on EKS(https://awslabs.github.io/ai-on-eks/)는 MkDocs가 아니라 **Docusaurus** 사이트입니다.
- 루트(`/`)는 React로 만든 **독립 스플래시 페이지**입니다. 사이드바 없이 히어로(제목·한 줄 소개·CTA)와 세 개의 기능 타일(Infrastructure / Blueprints / Guidance)만 보여줍니다.
- 실제 문서 안내는 `/docs/blueprints` 같은 **별도 소개 페이지**가 맡습니다. 이 페이지는 Training, Inference, Storage 등을 문단으로 설명하는 텍스트 중심 페이지입니다.
- 즉, "첫인상(피치)"과 "길 안내(오리엔테이션)"를 두 페이지로 나눈 구조입니다.

## 옵션 비교

| | 옵션 1 · 전용 스플래시 | 옵션 2 · 격상된 홈 (채택) |
|---|---|---|
| 구현 방식 | `overrides/home.html` 커스텀 템플릿 + 전용 CSS + `template:` front matter | 순수 Markdown (grid cards, admonition, button, mermaid, table) |
| 첫인상 | 전폭 히어로, 마케팅급 연출 가능 | 본문 폭(52rem) 안에서 연출 — 상대적으로 절제됨 |
| CSS/헤더 리스크 | 높음 — 헤더/탭 CSS가 취약하여 레이아웃 파손 위험 | 없음 — `extra.css`, `main.html` 무수정 |
| EN/KO 동기화 | 어려움 — 문구가 HTML/Jinja 안에 들어가 두 언어 분기 관리 필요 | 쉬움 — 두 `.md` 파일을 1:1로 비교·미러링 |
| 기여 난이도 | HTML/CSS 지식 필요, PR 리뷰 부담 | Markdown만 알면 누구나 수정 |
| 탐색성 | 사이드바 없음 → 첫 클릭 전까지 전체 구조가 안 보임 | 좌측 nav·탭이 그대로 보여 전체 구조 파악 쉬움 |
| 검색/접근성 | 커스텀 HTML은 검색 인덱싱·다크모드 대응을 직접 챙겨야 함 | Material 기본 동작 그대로 |

## 옵션 2 구현 원칙 (현재 홈 구성)

1. **히어로** — H1 + 굵은 한 줄 가치 제안 + 보조 문단 + CTA 버튼 2개
2. **작업 진행 중 안내** — `warning` admonition 1개
3. **솔루션 모션 4개 카드** — 페이지의 중심. Frugal AI를 첫 번째로 배치
4. **이 가이드의 특징** — 아이콘 헤더 4열 표 (카드 반복을 피해 시각적 리듬 변화)
5. **기반 영역** — AI Infra / NVIDIA GPU / 교육 및 행사 카드 3개
6. **대상 독자** — 역할별 bullet 목록
7. **전체 구성** — mermaid 흐름도 (워크로드 → 모션 → 가속기 → 실행 플랫폼)
8. **최신소식** — `note` admonition으로 최근 출시 1건 강조
9. **시작하기** — 3단계 번호 목록 + CTA 버튼

모든 H2에 명시적 앵커(`{ #solution-motions }` 등)를 붙여, 언어와 관계없이 같은 앵커로 링크할 수 있게 했습니다.

## 향후 옵션 1로 갈 경우 (STAGE 4 이후)

- `overrides/home.html` 을 새로 만들고 `docs/{en,ko}/index.md` front matter에 `template: home.html` 지정
- 스플래시 문구는 `main.html` 과 같은 방식(`config.theme.language` Jinja 분기)으로 로컬라이즈
- 현재 홈의 모션 카드/기반 영역 섹션은 스플래시 아래 Markdown 본문으로 그대로 재사용 가능
- 헤더 CSS 회귀 테스트(데스크톱/태블릿/모바일, 라이트/다크) 필수

## 가벼운 중간 단계 (선택)

CSS를 건드리지 않고 스플래시 느낌을 조금 더 내려면 홈 front matter에 Material 기본 기능인 `hide: [toc]` (또는 `hide: [navigation, toc]`)를 추가할 수 있습니다. 단, `main.html` 의 nav 접기 버튼 스크립트와의 상호작용을 `mkdocs serve` 로 확인한 뒤 적용하세요.
