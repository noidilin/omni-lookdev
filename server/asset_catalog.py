from __future__ import annotations

import os
from pathlib import Path


USD_EXTENSIONS = {".usd", ".usda", ".usdc"}
RELOAD_SNAPSHOT_PREFIX = "._lookdev_reload_"


class AssetCatalog:
    def __init__(self, asset_root: Path, extra_allowed_roots: list[Path] | None = None):
        self.asset_root = asset_root.resolve()
        self.extra_allowed_roots = [p.resolve() for p in (extra_allowed_roots or [])]

    def list_assets(self) -> list[dict[str, str]]:
        if not self.asset_root.exists():
            return []
        rows: list[dict[str, str]] = []
        for path in sorted(self.asset_root.rglob("*")):
            if self._is_user_asset(path):
                rows.append(
                    {
                        "id": path.relative_to(self.asset_root).as_posix(),
                        "name": path.name,
                        "path": path.relative_to(self.asset_root).as_posix(),
                    }
                )
        return rows

    def first_asset(self) -> Path | None:
        if not self.asset_root.exists():
            return None
        for path in sorted(self.asset_root.rglob("*")):
            if self._is_user_asset(path):
                return path.resolve()
        return None

    def resolve(self, requested: str) -> Path:
        if not requested:
            raise ValueError("Asset path is required")
        candidate = Path(requested)
        if not candidate.is_absolute():
            candidate = self.asset_root / candidate
        candidate = candidate.resolve()
        if candidate.suffix.lower() not in USD_EXTENSIONS:
            raise ValueError(f"Unsupported asset extension: {candidate.suffix}")
        if not candidate.exists():
            raise FileNotFoundError(str(candidate))
        allowed_roots = [self.asset_root, *self.extra_allowed_roots]
        if not any(os.path.commonpath([str(candidate), str(root)]) == str(root) for root in allowed_roots):
            raise PermissionError(f"Asset is outside allowed roots: {candidate}")
        return candidate

    def _is_user_asset(self, path: Path) -> bool:
        if not path.is_file() or path.suffix.lower() not in USD_EXTENSIONS:
            return False
        relative_parts = path.relative_to(self.asset_root).parts
        if any(part.startswith(".") for part in relative_parts):
            return False
        return not path.name.startswith(RELOAD_SNAPSHOT_PREFIX)
