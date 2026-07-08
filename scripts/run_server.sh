#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export OVRTX_SKIP_USD_CHECK=1
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$PWD/.cache}"
export CUDA_CACHE_PATH="${CUDA_CACHE_PATH:-$PWD/.cache/cuda}"
export __GL_SHADER_DISK_CACHE_PATH="${__GL_SHADER_DISK_CACHE_PATH:-$PWD/.cache/gl}"

mkdir -p "$XDG_CACHE_HOME" "$CUDA_CACHE_PATH" "$__GL_SHADER_DISK_CACHE_PATH" logs data/generated

source .venv/bin/activate
python3 -m server.ov_web_viewer_server "$@" 2>&1 | tee logs/server.log

