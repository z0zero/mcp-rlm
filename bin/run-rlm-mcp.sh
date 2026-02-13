#!/usr/bin/env bash
set -euo pipefail
REPO_DIR="/mnt/d/vibe-coding/mcp/rlm"
cd "$REPO_DIR"
export PYTHONPATH="$REPO_DIR/src"
exec "$REPO_DIR/.venv/bin/python" -m rlm_mcp.server
