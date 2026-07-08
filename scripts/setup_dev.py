from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / os.environ.get("VENV_DIR", ".venv")


def venv_python() -> Path:
    return VENV / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")


def run(args: list[str], cwd: Path = ROOT) -> None:
    print("+", " ".join(str(arg) for arg in args))
    subprocess.check_call(args, cwd=cwd)


def main() -> int:
    run([sys.executable, "-m", "venv", str(VENV)])
    py = venv_python()
    run([str(py), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    run([str(py), "-m", "pip", "install", "-r", str(ROOT / "server" / "requirements-dev.txt")])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
