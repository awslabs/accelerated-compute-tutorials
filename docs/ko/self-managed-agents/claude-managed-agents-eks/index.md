---
title: Claude Managed Agents on EKS (셀프 호스팅 샌드박스)
description: Anthropic Managed Agents의 실행 계층을 자체 EKS 클러스터에서 운영 — dispatcher가 Anthropic 작업 큐에서 툴 호출을 가져와 사전 예열된 gVisor 격리 샌드박스 Pod에 바인딩
---

# Claude Managed Agents on Amazon EKS — 셀프 호스팅 샌드박스

[Anthropic Managed Agents](https://platform.claude.com/docs/en/managed-agents)는 호스팅형 에이전트 루프입니다. Claude, 대화 상태, 환경별 작업 큐가 모두 Anthropic 컨트롤 플레인에서 실행됩니다. [셀프 호스팅 샌드박스](https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes)를 사용하면 오케스트레이션은 Anthropic 측에 그대로 두되 **툴 및 코드 실행만 여러분이 제어하는 인프라로 이동**합니다 — 여러분의 VPC 내부, 여러분의 egress 정책 아래, 여러분의 감사 제어 하에서. 에이전트의 파일, 프로세스, 네트워크 트래픽은 여러분의 환경에 머뭅니다.

이 가이드는 [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) 프로젝트를 사용해 그 실행 계층을 **Amazon EKS**에 배포합니다. Anthropic이 [GKE Agent Sandbox](https://agent-sandbox.sigs.k8s.io/docs/use-cases/anthropic-managed-agents/)용으로 공개한 레퍼런스 아키텍처를 Karpenter, gVisor 격리, EKS 네이티브 스토리지, Kubernetes 네트워크 정책 기반의 EKS 환경으로 각색했습니다.

!!! warning "프리뷰 소프트웨어"
    Anthropic 셀프 호스팅 샌드박스와 Agent Sandbox 프로젝트는 모두 초기 단계이며, API가 예고 없이 변경될 수 있습니다. 프로덕션 수준으로 하드닝된 구성이 아니라, 여러분의 배포를 위한 시작점으로 사용하세요.

## 언제 셀프 호스팅하는가

다음과 같은 경우에 셀프 호스팅이 적합합니다.

- 네트워크 경계를 벗어나면 안 되는 데이터를 에이전트가 다뤄야 할 때
- 공개 라우팅되지 않는 내부 서비스에 접근해야 할 때
- 조직 자체의 컴플라이언스/감사 제어 하에서 실행해야 할 때

해당 사항이 없다면 Anthropic 기본 매니지드 클라우드 샌드박스가 더 간단합니다.

## 왜 Warm Pool인가 (장기 실행 워커 N개가 아니라)

Anthropic의 가장 단순한 레퍼런스는 "`ant beta:worker poll`을 N개 복제 실행"입니다. 동작은 하지만, 모든 복제본이 환경 키를 보유하고 `api.anthropic.com`으로의 egress를 상시 열어 두는 장기 실행 프로세스이며, 해당 복제본에 배정된 모든 세션이 동일한 `/workspace`를 공유합니다.

Agent Sandbox 프리미티브는 책임을 분리합니다.

- **작은 dispatcher 하나**가 큐를 폴링합니다. 신뢰할 수 없는 코드를 실행하지 않고 claim 바인딩만 수행합니다.
- **각 작업 항목마다 `SandboxClaim`을 생성**하여 `SandboxWarmPool`의 사전 예열된 Pod를 1초 미만에 바인딩하므로, 새 세션이 이미지 pull을 기다리지 않습니다.
- **Pod당 세션 하나.** Pod는 정확히 한 세션의 워커를 실행하고 세션 종료 시 폐기됩니다. 단일 샌드박스의 blast radius는 세션 하나입니다.
- **Warm Pool이 그 뒤에서 다시 채워져** 다음 세션도 빠르게 유지됩니다.

## 왜 Standard EKS + Karpenter인가 (Auto Mode가 아니라)

gVisor는 부팅 시 노드에 `runsc` containerd shim 설치가 필요합니다. EKS Auto Mode는 커스텀 AMI나 user-data를 허용하지 않아 이것이 불가능합니다. Karpenter 기반 Standard EKS는 커스텀 노드 구성(AL2023 user-data로 부팅 시 gVisor 설치), 전용 taint NodePool(격리 가능 노드에만 샌드박스 워크로드 배치), 빠른 오토스케일링을 제공합니다.

## 아키텍처

```
┌───────────────────────────┐          ┌──────────────────────────────────────────────┐
│  Anthropic 컨트롤 플레인    │          │  여러분의 Amazon EKS 클러스터 · Agent Sandbox │
│                            │          │                                                │
│   ┌──────────────┐         │  poll    │   ┌────────────┐                               │
│   │  work queue  │◀────────┼──────────┼───│ dispatcher │  (환경 키 보유,              │
│   └──────┬───────┘         │          │   └─────┬──────┘   신뢰 불가 코드 없음)        │
│          │ session_id      │          │         │ SandboxClaim                         │
│          │                 │          │         ▼                                      │
│          │                 │          │   ┌──────────────┐   binds   ┌──────────────┐  │
│          │                 │          │   │SandboxWarmPool│─────────▶│ worker pod   │  │
│          │                 │  ant     │   └──────────────┘           │ (gVisor)     │  │
│   ┌──────▼───────┐         │  worker  │                              │ ant worker   │  │
│   │  Claude loop │◀────────┼──run─────┼──────────────────────────────│ run          │  │
│   └──────────────┘  tool   │  results │                              └──────┬───────┘  │
│                     calls  │          │                                     │          │
└───────────────────────────┘          │                       /mnt/session/outputs     │
                                        │                              ▼                 │
                                        │                        ┌───────────┐           │
                                        │                        │ gp3 PVC   │           │
                                        │                        └───────────┘           │
                                        └──────────────────────────────────────────────┘
```

Anthropic 자격 증명은 두 가지이며, 이 둘을 분리하는 것이 보안 모델의 핵심입니다.

| 자격 증명 | 접두사 | 범위 | 위치 |
|-----------|--------|------|------|
| **환경 키 (Environment key)** | `sk-ant-oat01-...` | **한** 환경의 작업 ack + 툴 결과 게시 | dispatcher 및 worker Pod에만 |
| **조직 API 키 (Org API key)** | `sk-ant-api03-...` | 전체 API 접근 | **여러분의 로컬 머신에만** — 에이전트/세션 생성용, 클러스터에 절대 두지 않음 |

## 전체 동작 흐름

1. 셀프 호스팅 환경을 대상으로 세션을 생성합니다. Anthropic이 이를 작업 항목으로 큐에 넣습니다.
2. **dispatcher**가 작업 큐를 롱 폴링하여 항목을 claim하고, Warm Pool의 준비된 Pod를 바인딩하는 `SandboxClaim`을 생성합니다.
3. **지연 바인딩(late binding):** Pod는 어떤 세션을 처리할지 알기 전에 이미 실행 중이므로 session ID를 컨테이너 env var로 전달할 수 없습니다. 워커 이미지는 작은 HTTP 리스너를 실행하고 dispatcher가 `{session_id, work_id}`를 POST할 때까지 대기합니다.
4. 그 후 워커가 `ant beta:worker run`을 exec합니다. `ant`는 작업 항목을 ack하고, 에이전트의 skills와 memory store를 다운로드하고, 각 툴 호출을 로컬에서 실행하며, 결과를 `api.anthropic.com`으로 스트리밍합니다.
5. 세션이 유휴 상태가 되면 워커가 종료되고, 컨트롤러가 샌드박스를 삭제하며, Warm Pool이 새 교체본을 띄웁니다.

---

## 사전 준비

- **Karpenter**, **EBS CSI driver** 애드온, 그리고 `NetworkPolicy`를 강제하는 CNI(네트워크 정책이 활성화된 VPC CNI 또는 Cilium)를 갖춘 **Amazon EKS Standard 클러스터**(1.30+).
- 클러스터에 설치된 **Agent Sandbox 컨트롤러**(`agents.x-k8s.io` 및 `extensions.agents.x-k8s.io` CRD 제공). [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) 참고. 여기 매니페스트는 `v1alpha1`을 사용합니다. 컨트롤러가 v1beta1을 제공하면 dispatcher에 `SANDBOX_API_VERSION=v1beta1`을 설정하세요.
- PATH에 `kubectl`, `kustomize`, `docker buildx`, AWS CLI.
- **Managed Agents 접근 권한이 있는 Anthropic 계정**, **조직 API 키**, 그리고 로컬에 설치된 **Anthropic CLI**(`ant`):

    ```bash
    ANT_VERSION=1.9.1
    ARCH=$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')
    case "$(uname -s)" in
      Darwin) curl -fsSL "https://github.com/anthropics/anthropic-cli/releases/download/v${ANT_VERSION}/ant_${ANT_VERSION}_macos_${ARCH}.zip" -o /tmp/ant.zip && sudo unzip -o /tmp/ant.zip ant -d /usr/local/bin && rm /tmp/ant.zip ;;
      Linux)  curl -fsSL "https://github.com/anthropics/anthropic-cli/releases/download/v${ANT_VERSION}/ant_${ANT_VERSION}_linux_${ARCH}.tar.gz" | sudo tar -xz -C /usr/local/bin ant ;;
    esac
    ant --version
    ```

    다운로드가 404라면 [Anthropic CLI 릴리스](https://github.com/anthropics/anthropic-cli/releases)에서 최신 버전을 확인하세요.

가이드 전반에서 사용하는 공용 셸 변수를 설정합니다.

```bash
export CLUSTER_NAME=my-eks-cluster
export AWS_REGION=us-west-2
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR=${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
```

---

## 모듈 1 — Anthropic에서 셀프 호스팅 환경 생성

환경은 Anthropic의 에이전트 루프와 여러분의 클러스터를 연결하는 작업 큐입니다. [Anthropic Console](https://platform.claude.com/)에서 **Self-hosted** 타입으로 생성(**Environments → New → Self-hosted**)하거나 API로 생성합니다.

```bash
export ANTHROPIC_API_KEY=sk-ant-api03-YOUR_ORG_KEY   # 조직 키, 이 명령에만 사용

curl https://api.anthropic.com/v1/environments \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "anthropic-beta: managed-agents-2026-04-01" \
  -H "content-type: application/json" \
  -d '{"name":"eks-agent-sandbox","config":{"type":"self_hosted"}}'
```

두 값을 수집합니다.

- **Environment ID**(`env_01...`) — API 응답의 `id`, 또는 환경 상세 페이지 Console URL.
- **Environment key**(`sk-ant-oat01-...`) — Console에서 환경을 열고 **Generate environment key** 클릭. 키는 Console에서만 생성할 수 있습니다.

```bash
export ANTHROPIC_ENVIRONMENT_ID=env_01...
export ANTHROPIC_ENVIRONMENT_KEY=sk-ant-oat01-...
```

**체크포인트:** `env_...` ID와 `sk-ant-oat01-...` 키를 모두 확보했습니다.

---

## 모듈 2 — 이미지 빌드 및 푸시

이미지는 두 개입니다. **worker**(`ant` + 디스패치 리스너 포함)와 **dispatcher**(큐 폴링, claim 바인딩). 둘 다 Graviton용 `linux/arm64`를 타깃합니다.

```bash
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR"

for repo in claude-agent-worker claude-agent-dispatcher; do
  aws ecr describe-repositories --repository-names "$repo" --region "$AWS_REGION" >/dev/null 2>&1 \
    || aws ecr create-repository --repository-name "$repo" --region "$AWS_REGION" >/dev/null
done

docker buildx build --platform linux/arm64 \
  -t "$ECR/claude-agent-worker:latest" --push src/worker

docker buildx build --platform linux/arm64 \
  -t "$ECR/claude-agent-dispatcher:latest" --push src/dispatcher
```

**체크포인트:** 두 리포지토리에 `latest` 이미지가 보입니다.

```bash
aws ecr list-images --repository-name claude-agent-worker --region "$AWS_REGION"
aws ecr list-images --repository-name claude-agent-dispatcher --region "$AWS_REGION"
```

---

## 모듈 3 — 샌드박스 인프라 배포

환경 키를 Secret으로 저장합니다(커밋보다 이 방식을 권장. 프로덕션에서는 Secrets Store CSI driver나 External Secrets Operator로 AWS Secrets Manager에서 소싱):

```bash
kubectl create namespace claude-agents --dry-run=client -o yaml | kubectl apply -f -
kubectl -n claude-agents create secret generic anthropic-env-key \
  --from-literal=ANTHROPIC_ENVIRONMENT_KEY="$ANTHROPIC_ENVIRONMENT_KEY"
```

매니페스트 플레이스홀더를 채우고 kustomization을 적용합니다.

```bash
cd k8s
sed -i.bak "s|ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com|$ECR|g" sandboxtemplate-worker.yaml dispatcher.yaml
sed -i.bak "s|ENV_ID|$ANTHROPIC_ENVIRONMENT_ID|g" dispatcher.yaml
sed -i.bak "s|\${CLUSTER_NAME}|$CLUSTER_NAME|g" nodepool-gvisor.yaml
rm -f *.bak

kubectl apply -k .
```

**체크포인트:** dispatcher가 폴링 중이고 Warm Pool에 준비된 워커가 있습니다(최초 적용 시 Karpenter가 gVisor 노드를 프로비저닝하는 데 약 2분 소요).

```bash
kubectl -n claude-agents get sandboxwarmpool,pods
```

```
NAME                                                            REPLICAS
sandboxwarmpool.extensions.agents.x-k8s.io/claude-agent-worker   2

NAME                                            READY   STATUS    RESTARTS   AGE
pod/claude-agent-dispatcher-xxxxxxxxxx-xxxxx    1/1     Running   0          2m
pod/claude-agent-worker-xxxxx                   1/1     Running   0          2m
pod/claude-agent-worker-yyyyy                   1/1     Running   0          2m
```

워커가 3분 넘게 `Pending`이면 Karpenter가 아직 gVisor 노드를 프로비저닝 중입니다. `kubectl -n claude-agents describe pod -l app=claude-agent-worker`에서 스케일업 이벤트를 확인하세요.

---

## 모듈 4 — Managed Agent 연결 및 검증

CLI 인증 후, 대화형 명령에서 OAuth 토큰을 가리지 않도록 조직 API 키를 unset합니다.

```bash
ant auth login
unset ANTHROPIC_API_KEY
```

환경에 바인딩된 에이전트와 세션을 생성합니다.

```bash
AGENT_ID=$(ant beta:agents create \
  --name eks-sandbox-probe \
  --model '{"id":"claude-sonnet-4-6"}' \
  --system 'You run tools inside a self-hosted sandbox on EKS under gVisor. Use bash to inspect the environment when asked.' \
  --tool '{"type":"agent_toolset_20260401"}' \
  --format json --transform 'id' -r)

SESSION_ID=$(ant beta:sessions create \
  --agent '{"id":"'"$AGENT_ID"'","type":"agent"}' \
  --environment-id "$ANTHROPIC_ENVIRONMENT_ID" \
  --format json --transform 'id' -r)

echo "AGENT_ID=$AGENT_ID  SESSION_ID=$SESSION_ID"
```

툴 호출을 유발하는 프롬프트를 보내고, 잠시 대기한 뒤 응답을 읽습니다.

```bash
ant beta:sessions:events send --session-id "$SESSION_ID" \
  --event '{"type":"user.message","content":[{"type":"text","text":"Run `uname -a && hostname` and tell me what sandbox you are executing in."}]}'

sleep 15

ant beta:sessions:events list --session-id "$SESSION_ID" --order asc --format jsonl \
  | jq -r 'select(.type=="agent.message") | .content[0].text'
```

**체크포인트:** 모델이 gVisor 커널(`4.4.0` 문자열은 gVisor의 합성 커널 시그니처)과 `claude-agent-worker-*` 호스트명을 보고합니다 — `bash`가 Anthropic이 아니라 **여러분의** 클러스터 Pod에서 실행되었다는 증거입니다. 클러스터 측에서도 확인합니다.

```bash
kubectl -n claude-agents logs -l app=claude-agent-worker --tail=20 --prefix
```

이제 `--environment-id "$ANTHROPIC_ENVIRONMENT_ID"`로 생성한 모든 세션은 여기서 툴 호출을 실행합니다.

!!! note "ant 1.9.1 플래그 파싱"
    `--model`과 `--agent`는 `--help` 상 문자열을 받지만 ant 1.9.1은 JSON 객체 형태만 파싱합니다 — `'{"id":"..."}'`로 전달하세요. 검사는 `events stream`보다 `events list`를 권장합니다. `stream`은 연결 이후 도착한 이벤트만 방출합니다.

---

## Warm Pool 오토스케일링

`SandboxWarmPool`은 고정 `replicas: 2`로 배포됩니다. 실제 트래픽에서는 큐 depth로 스케일하세요. 두 가지 방법:

- **`/scale` 서브리소스에 HPA.** `SandboxWarmPool`은 `/scale`을 노출하므로 `HorizontalPodAutoscaler`가 커스텀/외부 메트릭으로 이를 타깃할 수 있습니다.
- **stats-adapter 사이드카.** 작은 프로세스가 약 15초마다 Anthropic `work.stats` 엔드포인트를 읽고 동시 세션 수에 맞춰 Warm Pool 복제본 수를 patch합니다. 이 경로는 **조직 API 키**가 필요하므로 dispatcher 네임스페이스에만 두고 worker Pod에는 절대 두지 마세요. 동작하는 `stats-adapter`는 Anthropic의 [GKE 레퍼런스 구현](https://github.com/GoogleCloudPlatform/kubernetes-engine-samples/tree/main/ai-ml/anthropic-agent-sandbox)을 참고하세요.

---

## 보안 모델 — 여러분의 책임

셀프 호스팅 시 Anthropic은 컨트롤 플레인만 보호합니다. 다음은 **여러분의** 책임입니다([Anthropic 보안 모델](https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes-security) 참고).

- **런타임 하드닝.** 이 레시피는 워커를 non-root, 읽기 전용 루트 파일시스템, 모든 capability drop, 서비스 어카운트 토큰 미마운트, gVisor 격리로 실행합니다. 이 기본값을 유지하세요.
- **네트워크 egress.** default-deny `NetworkPolicy` + allow-list가 기반 계층입니다. `NetworkPolicy`는 호스트명을 매칭할 수 없어 HTTPS 규칙이 넓은 `0.0.0.0/0:443`입니다. AWS Network Firewall FQDN 규칙, Cilium `toFQDNs` 정책, egress 프록시 등 호스트명 인식 제어로 `api.anthropic.com`으로 좁히세요.
- **키 저장과 로테이션.** 환경 키는 이미지가 아니라 시크릿 매니저에 두세요. 노출 의심 시 즉시 로테이션하면 워커의 다음 호출부터 revocation이 적용됩니다.
- **신뢰 경계 격리.** 환경 키는 한 환경의 큐로 스코프됩니다. 신뢰할 수 없는 멀티테넌트 워크로드는 신뢰 경계마다 별도 workspace/환경을 두어 각 키가 단일 테넌트 세션에만 매핑되도록 하세요.
- **세션 데이터.** 대화 내용과 툴 출력은 워커와 `/mnt/session/outputs` PVC를 거칩니다. 이 데이터의 보존·마스킹·삭제는 여러분 책임입니다.
- **Memory store.** 워커는 세션 동안 `/mnt/memory/`에 작업 복사본을 두고 teardown 시 삭제합니다. teardown 없이 종료한 워커는 복사본을 남길 수 있으니, 잔여 복사본을 정리하고 세션 간 격리를 유지하세요.

---

## 정리

```bash
# Anthropic 세션 삭제
ant beta:sessions list --format jsonl | jq -r '.id' \
  | xargs -I{} ant beta:sessions delete --session-id {}

# 클러스터 리소스 제거
kubectl -n claude-agents delete sandboxclaim --all
kubectl delete -k k8s
kubectl delete namespace claude-agents
```

더 이상 필요 없다면 ECR 리포지토리와 Anthropic Console의 셀프 호스팅 환경도 삭제하세요.

---

## 다음 단계

- **에이전트에 내부 툴 제공.** egress 정책을 여러분의 내부 서비스로 향하게 하거나, 커스텀 툴/네트워크 내 MCP 서버를 워커 이미지(`src/worker/`)에 포함하세요. 이것이 셀프 호스팅의 핵심입니다.
- **egress 하드닝** — 호스트명 인식 제어로 정확히 `api.anthropic.com`으로 제한.
- **오토스케일링 추가** — Warm Pool이 수요를 추종하도록.

## 참고 자료

- [Anthropic — Self-hosted sandboxes](https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes)
- [Anthropic — Self-hosted sandbox security model](https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes-security)
- [Agent Sandbox — Anthropic Managed Agents use case](https://agent-sandbox.sigs.k8s.io/docs/use-cases/anthropic-managed-agents/)
- [GKE 레퍼런스 구현](https://github.com/GoogleCloudPlatform/kubernetes-engine-samples/tree/main/ai-ml/anthropic-agent-sandbox)
- [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox)
