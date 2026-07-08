#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r server/requirements.txt

python - <<'PY'
import importlib
for name in ("ovrtx", "ovstream", "warp", "numpy"):
    importlib.import_module(name)
    print(f"ok: import {name}")
PY
