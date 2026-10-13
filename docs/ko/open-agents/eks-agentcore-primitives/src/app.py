"""
Strands agent wrapped in the Bedrock AgentCore harness (BedrockAgentCoreApp),
hosted on EKS and consuming AgentCore managed services.

The harness exposes:
  - POST /invocations   (agent interaction)
  - GET  /ping          (health check)
on port 8080, matching the AgentCore Runtime container contract.

Conversation state is persisted in AgentCore Memory via Strands' built-in
AgentCoreMemorySessionManager — the framework rehydrates prior turns and saves
new ones automatically, so there is no manual load/save plumbing.
"""
import os
import logging

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentcore-harness")

# ---- Configuration (from env / EKS Pod Identity) ---------------------------
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
MODEL_ID = os.environ.get(
    "MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"
)
MEMORY_ID = os.environ.get("AGENTCORE_MEMORY_ID")          # AgentCore Memory resource id
GATEWAY_URL = os.environ.get("AGENTCORE_GATEWAY_URL")      # AgentCore Gateway MCP endpoint
# AgentCore Identity: outbound OAuth2 credential provider used to broker tokens
# for downstream APIs/tools the agent calls (e.g. through the Gateway).
IDENTITY_PROVIDER = os.environ.get("AGENTCORE_OAUTH_PROVIDER")  # credential provider name
IDENTITY_SCOPES = os.environ.get("AGENTCORE_OAUTH_SCOPES", "")  # space-delimited scopes
# AgentCore Browser: managed, sandboxed headless Chrome the agent can drive.
ENABLE_BROWSER = os.environ.get("AGENTCORE_BROWSER_ENABLED", "false").lower() == "true"
BROWSER_IDENTIFIER = os.environ.get("AGENTCORE_BROWSER_ID", "aws.browser.v1")

# Shared boto3 session — credentials come from EKS Pod Identity on the pod's ServiceAccount.
session = boto3.Session(region_name=AWS_REGION)

# ---- The harness ------------------------------------------------------------
app = BedrockAgentCoreApp()

# ---- Model ------------------------------------------------------------------
bedrock_model = BedrockModel(model_id=MODEL_ID, boto_session=session)

SYSTEM_PROMPT = (
    "You are a helpful assistant hosted on EKS using the Bedrock AgentCore harness. "
    "Use anything you know about the user from earlier turns to give helpful answers."
)


def _identity_token(actor_id: str) -> str | None:
    """
    Broker an outbound OAuth2 token via AgentCore Identity.

    AgentCore Identity holds the credential provider configuration; the agent
    exchanges it for a short-lived access token used on downstream/tool calls
    (e.g. through the Gateway), so per-user credentials are never baked into the
    image. Returns None when Identity is not configured (best-effort).
    """
    if not IDENTITY_PROVIDER:
        return None
    client = session.client("bedrock-agentcore")
    try:
        resp = client.get_resource_oauth2_token(
            resourceCredentialProviderName=IDENTITY_PROVIDER,
            scopes=[s for s in IDENTITY_SCOPES.split() if s],
            oauth2Flow="M2M",           # machine-to-machine; use USER_FEDERATION for on-behalf-of
            workloadIdentityToken=actor_id,
        )
        return resp.get("accessToken")
    except Exception as exc:  # non-fatal: fall back to no outbound token
        logger.warning("identity token broker failed: %s", exc)
        return None


def _memory_session_manager(actor_id: str, session_id: str):
    """
    Build a Strands AgentCoreMemorySessionManager for this (actor, session).

    Strands uses it to automatically rehydrate prior conversation turns and to
    persist new ones in AgentCore Memory — no manual list_events/create_event.
    Must be built per request because it is keyed on actor_id/session_id.
    Returns None when Memory is not configured (agent runs stateless).
    """
    if not MEMORY_ID:
        return None
    try:
        from bedrock_agentcore.memory.integrations.strands.config import (
            AgentCoreMemoryConfig,
        )
        from bedrock_agentcore.memory.integrations.strands.session_manager import (
            AgentCoreMemorySessionManager,
        )

        config = AgentCoreMemoryConfig(
            memory_id=MEMORY_ID,
            actor_id=actor_id,
            session_id=session_id,
        )
        return AgentCoreMemorySessionManager(config, region_name=AWS_REGION)
    except Exception as exc:  # non-fatal: fall back to stateless
        logger.warning("memory session manager init skipped: %s", exc)
        return None


def _build_agent(identity_token: str | None, session_manager) -> Agent:
    """Construct a Strands agent.

    - Conversation memory is handled by the AgentCore session manager (if any).
    - Tools come from AgentCore Gateway (MCP) and, optionally, the Browser tool.
    """
    # If a Gateway MCP endpoint is configured, attach it as an MCP tool provider.
    # AgentCore Identity brokers the outbound token so tool calls are authorized
    # per the configured credential provider.
    tools = []
    if GATEWAY_URL:
        try:
            from strands.tools.mcp import MCPClient

            # Strands builds the streamable-HTTP transport from `url` itself — do not
            # import mcp.client.streamable_http directly (its symbol names churn across
            # mcp 1.x/2.x). Headers are a first-class kwarg; attach the AgentCore
            # Identity-brokered Bearer token when present. For the NONE-authorizer demo
            # Gateway no token is needed, so headers is omitted.
            # continue_on_error: if the Gateway is unreachable, log and yield no tools
            # instead of raising — one bad server shouldn't take down the agent.
            if identity_token:
                gateway = MCPClient(
                    url=GATEWAY_URL,
                    headers={"Authorization": f"Bearer {identity_token}"},
                    continue_on_error=True,
                )
            else:
                gateway = MCPClient(url=GATEWAY_URL, continue_on_error=True)
            tools.append(gateway)
        except Exception as exc:
            logger.warning("gateway/MCP wiring skipped: %s", exc)

    # AgentCore Browser: a managed, sandboxed headless Chrome the agent can
    # navigate/scrape. The tool connects to an AWS-hosted browser session over
    # CDP; nothing runs a browser inside the pod except the Playwright driver.
    if ENABLE_BROWSER:
        try:
            from strands_tools.browser import AgentCoreBrowser

            browser_tool = AgentCoreBrowser(
                region=AWS_REGION, identifier=BROWSER_IDENTIFIER
            )
            tools.append(browser_tool.browser)
        except Exception as exc:
            logger.warning("agentcore browser wiring skipped: %s", exc)

    agent_kwargs = dict(model=bedrock_model, system_prompt=SYSTEM_PROMPT, tools=tools)
    if session_manager is not None:
        agent_kwargs["session_manager"] = session_manager
    return Agent(**agent_kwargs)


@app.entrypoint
def invoke(payload: dict) -> dict:
    """
    AgentCore invocation entrypoint.

    payload shape (matches AgentCore contract):
      {"input": {"prompt": "...", "actorId": "...", "sessionId": "..."}}
    """
    data = payload.get("input", payload)
    prompt = data.get("prompt", "")
    actor_id = data.get("actorId", "anonymous")
    session_id = data.get("sessionId", "default-session")

    if not isinstance(prompt, str) or not prompt.strip():
        return {"error": "input.prompt must be a non-empty string"}

    identity_token = _identity_token(actor_id)
    session_manager = _memory_session_manager(actor_id, session_id)

    # The session manager buffers/flushes memory writes; close it when done so
    # nothing is left unflushed (important if batch_size > 1 is ever set).
    try:
        agent = _build_agent(identity_token, session_manager)
        result = agent(prompt)
        answer = str(result.message) if hasattr(result, "message") else str(result)
    finally:
        if session_manager is not None and hasattr(session_manager, "close"):
            try:
                session_manager.close()
            except Exception as exc:
                logger.warning("session manager close failed: %s", exc)

    return {"output": {"message": answer}}


if __name__ == "__main__":
    # Bind 0.0.0.0 so the EKS readiness probe and Service can reach the pod.
    # (Default host is 127.0.0.1, which works on AgentCore Runtime's loopback
    # invoke but is unreachable from the kubelet probe / Service on EKS.)
    app.run(host="0.0.0.0")
