from __future__ import annotations

import argparse
from pathlib import Path

from .config import ServerConfig
from .runtime import LookdevRuntime, RuntimeNotAvailable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lookdev Studio ovrtx/ovstream server")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--signaling-port", type=int, default=49100)
    parser.add_argument("--health-port", type=int, default=8081)
    parser.add_argument("--public-ip", default="127.0.0.1")
    parser.add_argument("--asset-root", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = ServerConfig(
        width=args.width,
        height=args.height,
        fps=args.fps,
        signaling_port=args.signaling_port,
        health_port=args.health_port,
        public_ip=args.public_ip,
        asset_root=args.asset_root.resolve() if args.asset_root else ServerConfig().asset_root,
    )
    try:
        LookdevRuntime(config).start()
    except RuntimeNotAvailable as exc:
        print(str(exc))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

