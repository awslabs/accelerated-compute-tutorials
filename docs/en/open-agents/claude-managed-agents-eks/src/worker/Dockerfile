# Worker image for Anthropic Managed Agents self-hosted sandboxes on EKS.
#
# The image ships the Anthropic CLI (`ant`) plus a tiny Python listener. The warm
# pod blocks in entrypoint.py until the dispatcher POSTs its session binding, then
# execs `ant beta:worker run`. Build multi-arch (arm64 for Graviton nodes).
#
#   docker buildx build --platform linux/arm64 \
#     -t <acct>.dkr.ecr.<region>.amazonaws.com/claude-agent-worker:latest --push .
FROM debian:12-slim

ARG ANT_VERSION=1.9.1
ARG NODE_VERSION=22

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash \
      ca-certificates \
      curl \
      tar \
      unzip \
      python3 \
    && curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install the Anthropic CLI for the target architecture.
ARG TARGETARCH
RUN ARCH=$([ "${TARGETARCH:-arm64}" = "amd64" ] && echo amd64 || echo arm64) \
    && curl -fsSL "https://github.com/anthropics/anthropic-cli/releases/download/v${ANT_VERSION}/ant_${ANT_VERSION}_linux_${ARCH}.tar.gz" \
       | tar -xz -C /usr/local/bin ant \
    && ant --version

# Non-root user, writable workspace + output/session mount points.
RUN useradd --create-home --uid 1000 worker \
    && mkdir -p /workspace /mnt/session /mnt/outputs \
    && chown -R worker:worker /workspace /mnt/session /mnt/outputs

COPY --chown=worker:worker entrypoint.py /usr/local/bin/entrypoint.py

USER worker
WORKDIR /workspace

ENTRYPOINT ["python3", "/usr/local/bin/entrypoint.py"]
