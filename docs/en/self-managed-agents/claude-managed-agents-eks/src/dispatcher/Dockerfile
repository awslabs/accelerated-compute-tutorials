# Dispatcher image: polls the Anthropic work queue and binds SandboxClaims.
#
#   docker buildx build --platform linux/arm64 \
#     -t <acct>.dkr.ecr.<region>.amazonaws.com/claude-agent-dispatcher:latest --push .
FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim

ENV UV_SYSTEM_PYTHON=1
WORKDIR /app

COPY pyproject.toml ./
RUN uv pip install --no-cache -r pyproject.toml

COPY main.py ./

USER 1000
ENTRYPOINT ["python", "/app/main.py"]
