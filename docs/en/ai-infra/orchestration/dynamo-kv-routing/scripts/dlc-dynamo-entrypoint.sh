#!/usr/bin/env bash
# SPDX-License-Identifier: MIT-0
#
# Entrypoint that turns the AWS vLLM Deep Learning Container into a Dynamo
# component. Mounted into every Dynamo pod from the `dynamo-dlc-launcher`
# ConfigMap at /opt/lab.
#
#   dlc-dynamo-entrypoint.sh frontend [dynamo.frontend args...]
#   dlc-dynamo-entrypoint.sh worker   [dynamo.vllm args...]
#
# The DLC already ships vLLM, PyTorch, CUDA, NIXL, and runai-model-streamer.
# It does not ship Dynamo, so on first start this installs the pure-Python
# `ai-dynamo` wheel and its small Rust runtime wheel (`ai-dynamo-runtime`).
# It deliberately installs WITHOUT the `[vllm]` extra, so the DLC's vLLM,
# torch, and CUDA stack are left untouched. Dynamo 1.4.0 is built against
# vLLM 0.26.0, which is the vLLM version in the pinned DLC tag.
#
# For production, bake this into an image instead (see Dockerfile.dlc-dynamo).

set -euo pipefail

DYNAMO_VERSION="${DYNAMO_VERSION:-1.4.0}"
PY="$(command -v python3)"

installed_version() {
  "${PY}" - <<'EOF' 2>/dev/null || true
import importlib.metadata as m
try:
    print(m.version("ai-dynamo"))
except m.PackageNotFoundError:
    pass
EOF
}

if [[ "$(installed_version)" != "${DYNAMO_VERSION}" ]]; then
  echo "[lab] installing ai-dynamo==${DYNAMO_VERSION} into the DLC python (${PY})"
  start=$(date +%s)
  if command -v uv >/dev/null 2>&1; then
    # The DLC's interpreter is uv-managed; --break-system-packages lets uv
    # install into it. uv only adds what is missing and leaves vLLM alone.
    uv pip install --python "${PY}" --break-system-packages --no-progress \
      "ai-dynamo==${DYNAMO_VERSION}"
  else
    "${PY}" -m pip install --no-cache-dir --break-system-packages \
      "ai-dynamo==${DYNAMO_VERSION}"
  fi
  echo "[lab] ai-dynamo installed in $(( $(date +%s) - start ))s"
fi

"${PY}" - <<'EOF'
import importlib.metadata as m
print("[lab] versions:", {p: m.version(p) for p in ("ai-dynamo", "ai-dynamo-runtime", "vllm", "torch", "runai-model-streamer")})
EOF

role="${1:?usage: dlc-dynamo-entrypoint.sh frontend|worker [args...]}"
shift

case "${role}" in
  frontend)
    exec "${PY}" -m dynamo.frontend "$@"
    ;;
  worker)
    exec "${PY}" -m dynamo.vllm "$@"
    ;;
  *)
    echo "unknown role: ${role} (expected frontend or worker)" >&2
    exit 2
    ;;
esac
