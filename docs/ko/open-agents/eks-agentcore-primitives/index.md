---
title: Agents on EKS with AgentCore Primitives
description: Bedrock AgentCore 하니스(SDK 컨트랙트)로 감싼 Strands 에이전트를 Amazon EKS에서 호스팅하고, AgentCore 관리형 서비스(Memory/Gateway/Identity)를 소비하는 최소 레시피
---

# Agents on EKS with AgentCore Primitives — Minimal Walkthrough

## Overview

Build a [Strands](https://github.com/strands-agents/sdk-python) agent that uses the
**Amazon Bedrock AgentCore harness** — the `BedrockAgentCoreApp` SDK contract
(`POST /invocations` + `GET /ping` on port 8080) — but **host it yourself on Amazon EKS**
instead of the managed AgentCore Runtime. The agent consumes the AgentCore *managed
services* (Memory, Gateway, Identity) over the network via `boto3`/SDK.

This is the "bring the harness, own the runtime" pattern: you own the HTTP surface (a
Kubernetes `Service`/`Ingress` in front of your pods) and separately call the AgentCore
managed services from inside the agent. The same image stays deployable back to managed
AgentCore Runtime with no code changes.

| Component | Role |
|-----------|------|
| **Strands Agents SDK** | Orchestrates the agent reasoning loop |
| **`BedrockAgentCoreApp` (bedrock-agentcore SDK)** | The "harness" — serves `/invocations` + `/ping`, handles session context |
| **Amazon EKS (Graviton arm64)** | Hosts the harness container as a Deployment |
| **AgentCore Memory** | Short/long-term memory, called via SDK |
| **AgentCore Gateway** | Turns APIs/Lambdas into MCP tools for the agent |
| **AgentCore Identity** | Outbound auth and credential brokering for downstream/tool calls |
| **EKS Pod Identity** | Grants pods scoped access to Bedrock + AgentCore (no OIDC/annotation) |

!!! note "ARM64 is required by the AgentCore container contract"
    AgentCore Runtime requires `linux/arm64` images. Keeping the same constraint here keeps
    the image portable back to AgentCore Runtime, and Graviton is the cost/perf default on
    EKS. Build with `docker buildx --platform linux/arm64`.

---

## Architecture

```
                 ┌──────────────────────────────────────────────────────────────┐
                 │                Amazon EKS (Graviton arm64)                     │
   HTTP          │                                                                │
Client ────────▶ │  Ingress/Service ──▶  Pod(s): BedrockAgentCoreApp  (ASGI :8080)│
                 │                          │  GET  /ping         (health)         │
                 │                          │  POST /invocations                   │
                 │                          ▼                                      │
                 │                     Strands Agent                               │
                 │                          │                                      │
                 │        ┌─────────────────┼──────────────────┐                   │
                 │        ▼                 ▼                  ▼                    │
                 │  AgentCore Memory  AgentCore Gateway   Bedrock (LLM)             │
                 │   (boto3/SDK)       (MCP tools, via    (InvokeModel)             │
                 │        ▲            AgentCore Identity                           │
                 │        │             outbound token)                            │
                 │        └──── EKS Pod Identity role on the pod ServiceAccount ────│
                 └──────────────────────────────────────────────────────────────┘
```

**Data flow:**

1. A client sends `POST /invocations` to the EKS Service/Ingress.
2. The `BedrockAgentCoreApp` harness hands the payload to the Strands agent.
3. The agent loads/stores conversation context in **AgentCore Memory**.
4. **AgentCore Identity** brokers an outbound token; the agent calls tools exposed through
   **AgentCore Gateway** (MCP) with it.
5. The agent invokes the LLM on **Amazon Bedrock**.
6. The harness returns the response body on `/invocations`.

---

## Prerequisites

- An EKS cluster (1.30+) with **Graviton (arm64)** nodes. EKS Pod Identity needs no OIDC provider.
- AWS account with Bedrock model access.
- AgentCore Memory, Gateway, and Identity resources provisioned (or provision Memory inline below).
- `kubectl`, `docker` (with `buildx`), `aws` CLI installed.

---

## The agent (harness + Strands + AgentCore services)

The harness is `BedrockAgentCoreApp`. You decorate a single entrypoint with
`@app.entrypoint`; the SDK serves `/invocations` and `/ping` on port 8080 when you call
`app.run()`. Inside the entrypoint we wire the Strands agent, AgentCore Memory (session
manager), AgentCore Identity (outbound token), and AgentCore Gateway (MCP tools).

The buildable sources ship with this recipe under [`src/`](src/) — `app.py`,
`requirements.txt`, and the `Dockerfile`. The relevant wiring:

```python
# AgentCore Identity: broker a short-lived outbound OAuth2 token so API keys are
# never baked into the image. Attached as a Bearer header on the Gateway MCP client.
def _identity_token(actor_id: str) -> str | None:
    if not IDENTITY_PROVIDER:
        return None
    client = session.client("bedrock-agentcore")
    resp = client.get_resource_oauth2_token(
        resourceCredentialProviderName=IDENTITY_PROVIDER,
        scopes=[s for s in IDENTITY_SCOPES.split() if s],
        oauth2Flow="M2M",           # machine-to-machine
        workloadIdentityToken=actor_id,
    )
    return resp.get("accessToken")

# AgentCore Gateway: attach the MCP endpoint as a Strands tool provider. Strands
# builds the streamable-HTTP transport from `url` — pass the Gateway MCP URL and,
# when AgentCore Identity has brokered a token, the Bearer header. continue_on_error
# keeps a transiently-unreachable Gateway from taking down the whole agent.
if GATEWAY_URL:
    from strands.tools.mcp import MCPClient
    if identity_token:
        gateway = MCPClient(
            url=GATEWAY_URL,
            headers={"Authorization": f"Bearer {identity_token}"},
            continue_on_error=True,
        )
    else:
        gateway = MCPClient(url=GATEWAY_URL, continue_on_error=True)
    tools.append(gateway)

# AgentCore Memory: Strands' AgentCoreMemorySessionManager rehydrates prior turns
# and persists new ones automatically — no manual list_events/create_event.
```

- **Inbound auth** (who may call *your* `/invocations`) is enforced at the EKS edge — your
  Ingress/ALB with an OIDC/JWT authorizer, since you own the HTTP surface on EKS.
- **Outbound auth** (how the agent authenticates to *downstream* APIs and tools) is what
  Identity brokers via `get_resource_oauth2_token`, referenced by name through
  `AGENTCORE_OAUTH_PROVIDER`.

!!! tip "Why `BedrockAgentCoreApp` instead of hand-rolled FastAPI?"
    Using `BedrockAgentCoreApp` is what makes this specifically the **AgentCore harness**:
    it provides the `/invocations` + `/ping` contract, session context, and streaming, and
    keeps the exact same image deployable on managed AgentCore Runtime with no code changes.

---

## Run it: minimal live walkthrough (EKS + Memory + Gateway + Identity + Bedrock)

This is the smallest end-to-end path that proves the pattern on a **real cluster**: a Strands
agent, wrapped in the AgentCore harness, running as a pod on EKS, calling a **Bedrock** model,
persisting conversation state in **AgentCore Memory**, and calling a **working tool** through
**AgentCore Gateway** (a Lambda target you create in Step 3).

The commands below use a worked example on an **EKS Auto Mode** cluster in
`ap-southeast-1`; substitute your own values.

```bash
export AWS_REGION=ap-southeast-1
export CLUSTER_NAME=eks-automode
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR_REPO=${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
export APP_NAME=agentcore-harness-agent
export NAMESPACE=agents
# Claude Haiku 4.5 is cheap + fast; it is served via an inference profile. In
# ap-southeast-1 the Haiku 4.5 profile is a GLOBAL profile (there is no apac. one),
# so use the global. id — verify with: aws bedrock list-inference-profiles.
export MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0

# Identity (outbound auth) is OPTIONAL for this demo. The Lambda target below uses a
# GATEWAY_IAM_ROLE credential — the Gateway invokes the Lambda with its own service
# role, so no bearer token is needed. Leaving these unset makes the agent attach no
# Authorization header, which is exactly right for a NONE-authorizer Lambda target.
export AGENTCORE_OAUTH_PROVIDER=""   # set only when a target needs brokered OAuth
export AGENTCORE_OAUTH_SCOPES=""
# AGENTCORE_GATEWAY_URL is captured from Step 3 (create-gateway output), not hardcoded.
```

!!! note "Gateway + Identity in this minimal path"
    To keep the demo free of a Cognito user-pool detour, Step 3 creates the Gateway with
    `--authorizer-type NONE` (no inbound JWT) and a Lambda target whose credential is
    `GATEWAY_IAM_ROLE`. That is a **complete, working Gateway tool**. **AgentCore Identity**
    stays wired in the agent (`get_resource_oauth2_token`) and the IAM policy keeps that
    permission — it activates the moment you point `AGENTCORE_OAUTH_PROVIDER` at a credential
    provider for an OAuth-protected target. For production, front the Gateway with
    `CUSTOM_JWT` and enforce inbound auth at your EKS edge.

### Step 1 — Create the AgentCore Memory resource

```bash
# --event-expiry-duration is REQUIRED: an integer number of days (min 3, max 365)
# giving how long raw conversational events are retained. (The CLI help mislabels
# this as ISO-8601, but it parses the value as an integer.)
aws bedrock-agentcore-control create-memory \
  --name eks_harness_demo_memory \
  --event-expiry-duration 30 \
  --region ${AWS_REGION}

# Capture the id once ACTIVE. Note: list-memories entries expose `arn`/`id`/`status`
# but NOT `name`, so filter on the arn (which embeds the name) rather than name.
export AGENTCORE_MEMORY_ID=$(aws bedrock-agentcore-control list-memories \
  --region ${AWS_REGION} \
  --query "memories[?contains(arn, 'eks_harness_demo_memory')].id | [0]" --output text)
echo "MEMORY_ID=${AGENTCORE_MEMORY_ID}"
# (Simplest of all: the create-memory output already prints the id — just export it.)
```

### Step 2 — IAM: policy + Pod Identity role

Scope Bedrock to invoke, AgentCore to the Memory event/retrieve actions, plus the Gateway
invoke and the Identity token-broker action.

```bash
cat > demo-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "Bedrock", "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
      "Resource": "*" },
    { "Sid": "Memory", "Effect": "Allow",
      "Action": ["bedrock-agentcore:CreateEvent",
                 "bedrock-agentcore:ListEvents",
                 "bedrock-agentcore:RetrieveMemoryRecords",
                 "bedrock-agentcore:ListMemoryRecords"],
      "Resource": "*" },
    { "Sid": "GatewayAndIdentity", "Effect": "Allow",
      "Action": ["bedrock-agentcore:InvokeGateway",
                 "bedrock-agentcore:GetResourceOauth2Token"],
      "Resource": "*" }
  ]
}
EOF

aws iam create-policy --policy-name ${APP_NAME}-policy \
  --policy-document file://demo-policy.json

cat > trust-policy.json <<'EOF'
{ "Version": "2012-10-17",
  "Statement": [{ "Effect": "Allow",
    "Principal": { "Service": "pods.eks.amazonaws.com" },
    "Action": ["sts:AssumeRole", "sts:TagSession"] }] }
EOF

aws iam create-role --role-name ${APP_NAME}-role \
  --assume-role-policy-document file://trust-policy.json
aws iam attach-role-policy --role-name ${APP_NAME}-role \
  --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/${APP_NAME}-policy
```

!!! warning "Scope these actions down for production"
    The `Resource: "*"` above is for a getting-started walkthrough. In production, scope
    Bedrock to the specific model ARNs and AgentCore actions to the specific
    Memory/Gateway/credential-provider resource ARNs you provisioned.

!!! note "EKS Auto Mode"
    On an Auto Mode cluster the Pod Identity agent runs on AWS-managed compute (you will not
    see the `eks-pod-identity-agent` DaemonSet with ready pods in `kube-system`), but the
    **Pod Identity associations API works the same**. No addon install step is required.

### Step 3 — Create a working Gateway tool (Lambda function target)

Give the agent a real tool: a Lambda function exposed through AgentCore Gateway as an MCP
tool. The Gateway invokes the Lambda using its own service role (`GATEWAY_IAM_ROLE`
credential), and we use `--authorizer-type NONE` so no Cognito user pool is needed for the
demo.

**3a. Write and deploy the Lambda.** The function receives the tool arguments in the event
and returns a result. AgentCore passes the invoked tool name in the
`bedrock-agentcore-gateway-target-name` client context, but for a single tool you can just
read the arguments.

```bash
mkdir -p gateway-tool && cat > gateway-tool/index.py <<'EOF'
def handler(event, context):
    # Gateway delivers the tool's input arguments as the event payload.
    city = (event or {}).get("city", "the requested city")
    # A real tool would call a weather API here; we return a deterministic string
    # so the end-to-end path is easy to verify.
    return {"weather": f"It is 24C and sunny in {city}."}
EOF
( cd gateway-tool && zip -q function.zip index.py )

# Lambda needs a basic execution role.
cat > lambda-trust.json <<'EOF'
{ "Version": "2012-10-17",
  "Statement": [{ "Effect": "Allow",
    "Principal": { "Service": "lambda.amazonaws.com" },
    "Action": "sts:AssumeRole" }] }
EOF
aws iam create-role --role-name ${APP_NAME}-tool-role \
  --assume-role-policy-document file://lambda-trust.json
aws iam attach-role-policy --role-name ${APP_NAME}-tool-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
sleep 10  # let the role propagate

export TOOL_LAMBDA_ARN=$(aws lambda create-function \
  --function-name ${APP_NAME}-weather-tool \
  --runtime python3.12 --handler index.handler \
  --role arn:aws:iam::${ACCOUNT_ID}:role/${APP_NAME}-tool-role \
  --zip-file fileb://function.zip \
  --region ${AWS_REGION} \
  --query FunctionArn --output text)
echo "TOOL_LAMBDA_ARN=${TOOL_LAMBDA_ARN}"
```

**3b. Create the Gateway service role.** The Gateway assumes this role to invoke the Lambda.

```bash
cat > gw-trust.json <<'EOF'
{ "Version": "2012-10-17",
  "Statement": [{ "Effect": "Allow",
    "Principal": { "Service": "bedrock-agentcore.amazonaws.com" },
    "Action": "sts:AssumeRole" }] }
EOF
aws iam create-role --role-name ${APP_NAME}-gw-role \
  --assume-role-policy-document file://gw-trust.json

cat > gw-policy.json <<EOF
{ "Version": "2012-10-17",
  "Statement": [{ "Sid": "InvokeTool", "Effect": "Allow",
    "Action": "lambda:InvokeFunction",
    "Resource": "${TOOL_LAMBDA_ARN}" }] }
EOF
aws iam put-role-policy --role-name ${APP_NAME}-gw-role \
  --policy-name invoke-tool --policy-document file://gw-policy.json
sleep 10
```

**3c. Create the Gateway (MCP, no inbound auth for the demo).**

```bash
export GATEWAY_ID=$(aws bedrock-agentcore-control create-gateway \
  --name ${APP_NAME}-gw \
  --role-arn arn:aws:iam::${ACCOUNT_ID}:role/${APP_NAME}-gw-role \
  --protocol-type MCP \
  --authorizer-type NONE \
  --region ${AWS_REGION} \
  --query gatewayId --output text)

# The MCP endpoint the agent connects to.
export AGENTCORE_GATEWAY_URL=$(aws bedrock-agentcore-control get-gateway \
  --gateway-identifier ${GATEWAY_ID} --region ${AWS_REGION} \
  --query gatewayUrl --output text)
echo "GATEWAY_URL=${AGENTCORE_GATEWAY_URL}"
```

**3d. Attach the Lambda as an MCP tool target.** The `toolSchema` tells the agent what the
tool is called and what arguments it takes; `GATEWAY_IAM_ROLE` tells the Gateway to invoke
the Lambda with its own service role.

```bash
aws bedrock-agentcore-control create-gateway-target \
  --gateway-identifier ${GATEWAY_ID} \
  --name weather \
  --region ${AWS_REGION} \
  --target-configuration '{
    "mcp": {
      "lambda": {
        "lambdaArn": "'"${TOOL_LAMBDA_ARN}"'",
        "toolSchema": {
          "inlinePayload": [
            {
              "name": "get_weather",
              "description": "Get the current weather for a city.",
              "inputSchema": {
                "type": "object",
                "properties": { "city": { "type": "string", "description": "City name" } },
                "required": ["city"]
              }
            }
          ]
        }
      }
    }
  }' \
  --credential-provider-configurations '[{"credentialProviderType": "GATEWAY_IAM_ROLE"}]'
```

!!! note "NONE authorizer is for the demo only"
    `--authorizer-type NONE` means the Gateway does not authenticate inbound MCP calls — fine
    for a port-forwarded local test, not for production. The agent reaches the Gateway from
    inside the cluster; in production use `CUSTOM_JWT` and have **AgentCore Identity** broker
    the token (set `AGENTCORE_OAUTH_PROVIDER`), which the agent already attaches as a Bearer
    header when configured.

### Step 4 — Build + push the ARM64 image

Use the `src/` files that ship with this recipe.

```bash
cd src
aws ecr create-repository --repository-name ${APP_NAME} --region ${AWS_REGION} 2>/dev/null || true
aws ecr get-login-password --region ${AWS_REGION} \
  | docker login --username AWS --password-stdin ${ECR_REPO}
docker buildx create --use 2>/dev/null || true
docker buildx build --platform linux/arm64 \
  -t ${ECR_REPO}/${APP_NAME}:latest --push .
cd ..
```

### Step 5 — Deploy to EKS with Pod Identity

```bash
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
kubectl create serviceaccount ${APP_NAME}-sa -n ${NAMESPACE}

aws eks create-pod-identity-association \
  --cluster-name ${CLUSTER_NAME} --namespace ${NAMESPACE} \
  --service-account ${APP_NAME}-sa \
  --role-arn arn:aws:iam::${ACCOUNT_ID}:role/${APP_NAME}-role \
  --region ${AWS_REGION}

# Minimal Deployment — pin to an arm64 node so the AgentCore arm64 image runs natively.
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${APP_NAME}
  namespace: ${NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels: { app: ${APP_NAME} }
  template:
    metadata:
      labels: { app: ${APP_NAME} }
    spec:
      serviceAccountName: ${APP_NAME}-sa
      nodeSelector:
        kubernetes.io/arch: arm64
      containers:
        - name: agent
          image: ${ECR_REPO}/${APP_NAME}:latest
          ports: [{ containerPort: 8080 }]
          env:
            - { name: AWS_REGION, value: "${AWS_REGION}" }
            - { name: MODEL_ID, value: "${MODEL_ID}" }
            - { name: AGENTCORE_MEMORY_ID, value: "${AGENTCORE_MEMORY_ID}" }
            - { name: AGENTCORE_GATEWAY_URL, value: "${AGENTCORE_GATEWAY_URL}" }
            - { name: AGENTCORE_OAUTH_PROVIDER, value: "${AGENTCORE_OAUTH_PROVIDER}" }
            - { name: AGENTCORE_OAUTH_SCOPES, value: "${AGENTCORE_OAUTH_SCOPES}" }
          readinessProbe: { httpGet: { path: /ping, port: 8080 }, initialDelaySeconds: 10 }
---
apiVersion: v1
kind: Service
metadata:
  name: ${APP_NAME}
  namespace: ${NAMESPACE}
spec:
  selector: { app: ${APP_NAME} }
  ports: [{ port: 80, targetPort: 8080 }]
EOF

kubectl -n ${NAMESPACE} rollout status deploy/${APP_NAME}
```

### Step 6 — Verify: health, Bedrock, memory, and the Gateway tool

```bash
kubectl -n ${NAMESPACE} port-forward svc/${APP_NAME} 8080:80 &

# 1) Harness health contract
curl -s http://localhost:8080/ping                       # -> {"status":"healthy"}

# 2) Bedrock round-trip + first memory write (same actor/session both turns)
curl -s -X POST http://localhost:8080/invocations -H 'Content-Type: application/json' \
  -d '{"input":{"prompt":"My name is Wayne. Remember it.","actorId":"wayne","sessionId":"s1"}}'

# 3) New turn — the agent should recall the name from AgentCore Memory
curl -s -X POST http://localhost:8080/invocations -H 'Content-Type: application/json' \
  -d '{"input":{"prompt":"What is my name?","actorId":"wayne","sessionId":"s1"}}'

# 4) Exercise the Gateway tool — the agent calls get_weather over MCP, which the Gateway
#    routes to the Lambda target from Step 3. The reply should contain the Lambda's string.
curl -s -X POST http://localhost:8080/invocations -H 'Content-Type: application/json' \
  -d '{"input":{"prompt":"What is the weather in Singapore? Use your tools.","actorId":"wayne","sessionId":"s1"}}'
```

Call 3 answering "Wayne" proves state came back from **AgentCore Memory**. Call 4 returning
"It is 24C and sunny in Singapore." proves the agent discovered and invoked the **Gateway**
tool, which executed the **Lambda** target. The pod holds nothing between requests — Strands'
`AgentCoreMemorySessionManager` rehydrates the prior turns for `(actorId, sessionId)` on each
invocation and persists new ones, so any replica can serve any turn. You can confirm the
memory events landed independently:

```bash
aws bedrock-agentcore list-events \
  --memory-id ${AGENTCORE_MEMORY_ID} \
  --actor-id wayne --session-id s1 --include-payloads --region ${AWS_REGION}
```

!!! warning "If recall fails, suspect a poisoned session before suspecting the code"
    `AgentCoreMemorySessionManager` stores each turn as a JSON-serialized `SessionMessage`
    in the event's conversational `content.text`, and on read it does
    `json.loads(content.text)` over the **whole** session. If even one event in that
    `(actorId, sessionId)` holds non-JSON text — e.g. a plain string or a Python `repr`
    written by an earlier/buggy build — the read throws, is swallowed, and `list_messages`
    returns an **empty** list, so the agent loses *all* history for that session (not just
    the bad event). The fix is not an SDK change: use a **fresh `sessionId`**, or delete and
    recreate the Memory resource, after any run that may have written malformed events. Keep
    the entrypoint's persisted content JSON-serializable so you never seed a session with a
    value `json.loads` can't read back.

### Step 7 — Prove the agent is stateless across pods

The reason this recipe externalizes conversation state to AgentCore Memory is that **no pod
holds anything between requests** — so if the pod that served a turn disappears, a different
pod answers the next turn with full context. This is *statelessness / horizontal scalability*,
not HA failover: there is no standby, no session affinity, and no in-cluster state
replication. The proof is to delete the pod mid-conversation and watch context survive.

Use a **fresh `sessionId`** (a poisoned one — see the warning above — would make surviving
state look lost):

```bash
# Turn 1 — state something, and note which pod served it.
POD1=$(kubectl -n ${NAMESPACE} get pod -l app=${APP_NAME} -o jsonpath='{.items[0].metadata.name}')
echo "served by: ${POD1}"
kubectl -n ${NAMESPACE} port-forward svc/${APP_NAME} 8080:80 & PF=$!; sleep 4
curl -s -X POST http://localhost:8080/invocations -H 'Content-Type: application/json' \
  -d '{"input":{"prompt":"My name is Wayne and my favorite color is teal. Remember both.","actorId":"wayne","sessionId":"ha1"}}'
kill $PF

# Delete the exact pod that handled turn 1; the Deployment schedules a brand-new one.
kubectl -n ${NAMESPACE} delete pod ${POD1} --wait=true
kubectl -n ${NAMESPACE} rollout status deploy/${APP_NAME}
POD2=$(kubectl -n ${NAMESPACE} get pod -l app=${APP_NAME} -o jsonpath='{.items[0].metadata.name}')
echo "now served by: ${POD2}   (different pod, same session)"

# Turn 2 on the NEW pod — it recalls name AND color from AgentCore Memory.
kubectl -n ${NAMESPACE} port-forward svc/${APP_NAME} 8080:80 & PF=$!; sleep 4
curl -s -X POST http://localhost:8080/invocations -H 'Content-Type: application/json' \
  -d '{"input":{"prompt":"What is my name and favorite color?","actorId":"wayne","sessionId":"ha1"}}'
kill $PF
```

Turn 2 answering "Wayne" and "teal" from a pod that did not exist when you set them is the
proof: the pod that held the conversation was deleted, yet the context came back because it
lives in **AgentCore Memory**, not the pod. The same mechanism is what lets you scale
`replicas` up or roll the Deployment without pinning a user to a pod.

!!! note "This is statelessness, not failover testing"
    Deleting a pod demonstrates that state is external and any pod can serve any turn. Real
    high-availability testing — node loss, zonal failure, PodDisruptionBudgets, surge/maxUnavailable
    during rollouts, probe tuning — is a separate, larger exercise beyond this minimal
    walkthrough. For zero-dropped-requests during pod churn, run `replicas: 2+` (the full
    manifest in the implementation guide does) so a healthy pod is always in the Service while
    another is replaced.

### Same image on managed AgentCore Runtime

Because the image already implements the AgentCore container contract, you can deploy the
**same image** to managed AgentCore Runtime without code changes:

```python
import boto3
client = boto3.client("bedrock-agentcore-control", region_name="us-west-2")
client.create_agent_runtime(
    agentRuntimeName="agentcore_harness_agent",
    agentRuntimeArtifact={"containerConfiguration": {
        "containerUri": "ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com/agentcore-harness-agent:latest"
    }},
    networkConfiguration={"networkMode": "PUBLIC"},
    roleArn="arn:aws:iam::ACCOUNT_ID:role/AgentRuntimeRole",
)
```

The only differences are the hosting surface (EKS Service vs. managed microVM) and the IAM
mechanism (EKS Pod Identity vs. execution role). The harness and agent code are identical.

---

## Cleanup

```bash
kubectl delete deploy/${APP_NAME} svc/${APP_NAME} -n ${NAMESPACE} --ignore-not-found
kubectl delete namespace ${NAMESPACE} --ignore-not-found

# Remove the Pod Identity association (find its id first), then the role + policy
ASSOC_ID=$(aws eks list-pod-identity-associations \
  --cluster-name ${CLUSTER_NAME} --namespace ${NAMESPACE} \
  --query "associations[?serviceAccount=='${APP_NAME}-sa'].associationId" \
  --output text --region ${AWS_REGION})
aws eks delete-pod-identity-association \
  --cluster-name ${CLUSTER_NAME} --association-id ${ASSOC_ID} --region ${AWS_REGION}

aws iam detach-role-policy \
  --role-name ${APP_NAME}-role \
  --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/${APP_NAME}-policy
aws iam delete-role --role-name ${APP_NAME}-role
aws iam delete-policy --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/${APP_NAME}-policy
aws ecr delete-repository --repository-name ${APP_NAME} --force --region ${AWS_REGION}

# Delete the Memory resource
aws bedrock-agentcore-control delete-memory \
  --memory-id ${AGENTCORE_MEMORY_ID} --region ${AWS_REGION}

# Delete the Gateway tool target, the Gateway, then the Lambda + its roles.
# (List and delete targets first; a gateway cannot be deleted while targets exist.)
for TID in $(aws bedrock-agentcore-control list-gateway-targets \
  --gateway-identifier ${GATEWAY_ID} --region ${AWS_REGION} \
  --query 'items[].targetId' --output text); do
  aws bedrock-agentcore-control delete-gateway-target \
    --gateway-identifier ${GATEWAY_ID} --target-id ${TID} --region ${AWS_REGION}
done
aws bedrock-agentcore-control delete-gateway \
  --gateway-identifier ${GATEWAY_ID} --region ${AWS_REGION}

aws lambda delete-function --function-name ${APP_NAME}-weather-tool --region ${AWS_REGION}

aws iam delete-role-policy --role-name ${APP_NAME}-gw-role --policy-name invoke-tool
aws iam delete-role --role-name ${APP_NAME}-gw-role
aws iam detach-role-policy --role-name ${APP_NAME}-tool-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam delete-role --role-name ${APP_NAME}-tool-role
```

---

## Summary

- The AgentCore **harness** (`BedrockAgentCoreApp`) is just the `/invocations` + `/ping`
  HTTP contract on port 8080 — portable across managed Runtime and self-hosted EKS.
- On EKS you **own the HTTP surface** (Service/Ingress) and grant AWS access via **EKS Pod
  Identity** (fixed `pods.eks.amazonaws.com` trust, association maps role ↔ ServiceAccount).
- The AgentCore **managed services** — **Memory**, **Gateway**, and **Identity** — are
  consumed over the network via `boto3`/SDK regardless of where the harness runs. This
  walkthrough wires a **working Gateway tool** (a Lambda target the agent discovers and
  invokes over MCP) and keeps **Identity** ready for OAuth-protected targets.
- Keep the image `linux/arm64` so it stays deployable on both EKS Graviton nodes and managed
  AgentCore Runtime.
