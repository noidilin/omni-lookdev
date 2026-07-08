from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


LOOKDEV_ASSET_ROOT = "/LookdevAsset"
VIEWER_ROOTS = {"OVCamera", "Render", "TempChangeTracking", "ViewerLighting", "__Fabric_StageInfo"}
BOUND_ATTR_HINTS = ("bound", "bbox", "extent")


def parent_path(path: str) -> str:
    if path == "/" or path.count("/") <= 1:
        return "/"
    return path.rsplit("/", 1)[0]


class StageQueryCache:
    def __init__(self) -> None:
        self.paths: list[str] = []
        self.attrs: dict[str, dict[str, Any]] = {}
        self.child_index: dict[str, list[str]] = {}
        self.root_prim_path = "/"
        self.last_error = ""

    def refresh_from_renderer(self, renderer) -> None:
        try:
            result = renderer.query_prims(attribute_filter_mode=0)
        except TypeError:
            result = renderer.query_prims()
        self.attrs = dict(result)
        self.paths = sorted(self.attrs.keys())
        self.child_index = self._build_child_index(self.paths)
        self.root_prim_path = self._detect_root(self.paths, self.child_index)

    def refresh_from_usd_file(self, stage_path: Path) -> bool:
        code = r'''
import json
import sys
from pxr import Usd

stage = Usd.Stage.Open(sys.argv[1])
rows = []
if stage:
    for prim in stage.Traverse():
        rows.append({"path": str(prim.GetPath()), "typeName": prim.GetTypeName()})
print(json.dumps(rows))
'''
        try:
            completed = subprocess.run(
                [str(self._pxr_python()), "-c", code, str(stage_path)],
                capture_output=True,
                check=True,
                text=True,
                timeout=10,
            )
            rows = json.loads(completed.stdout or "[]")
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            self.last_error = f"OpenUSD hierarchy fallback failed: {detail or exc}"
            return False
        except Exception as exc:
            self.last_error = f"OpenUSD hierarchy fallback failed: {exc}"
            return False
        self.last_error = ""
        self.attrs = {str(row["path"]): {"typeName": str(row.get("typeName") or "")} for row in rows if row.get("path")}
        self.paths = sorted(self.attrs.keys())
        self.child_index = self._build_child_index(self.paths)
        self.root_prim_path = self._detect_root(self.paths, self.child_index)
        return bool(self.paths)

    def get_children(self, prim_path: str) -> list[dict[str, Any]]:
        rows = []
        for child in self.child_index.get(prim_path or self.root_prim_path, []):
            if parent_path(child) == "/" and child.rsplit("/", 1)[-1] in VIEWER_ROOTS:
                continue
            rows.append(
                {
                    "name": child.rsplit("/", 1)[-1] or child,
                    "path": child,
                    "type": self._classify(child),
                    "children": bool(self.child_index.get(child)),
                    "hasChildren": bool(self.child_index.get(child)),
                }
            )
        return rows

    def get_properties(self, prim_path: str) -> dict[str, Any]:
        attrs = self.attrs.get(prim_path, {})
        props: dict[str, Any] = {
            "path": prim_path,
            "name": prim_path.rsplit("/", 1)[-1] if prim_path else "",
            "type": self._classify(prim_path),
        }
        for name, value in attrs.items():
            props[str(name)] = str(value)
        return props

    def prim_count(self) -> int:
        return len(self.paths)

    def estimated_content_bounds(self) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
        mins: list[tuple[float, float, float]] = []
        maxes: list[tuple[float, float, float]] = []
        for path, attrs in self.attrs.items():
            if self._is_viewer_path(path):
                continue
            for name, value in attrs.items():
                if not any(hint in str(name).lower() for hint in BOUND_ATTR_HINTS):
                    continue
                numbers = self._numbers(value)
                if len(numbers) < 6:
                    continue
                lower = tuple(float(v) for v in numbers[:3])
                upper = tuple(float(v) for v in numbers[3:6])
                if all(upper[index] >= lower[index] for index in range(3)):
                    mins.append(lower)
                    maxes.append(upper)
        if not mins:
            return None
        lower = tuple(min(row[index] for row in mins) for index in range(3))
        upper = tuple(max(row[index] for row in maxes) for index in range(3))
        center = tuple((lower[index] + upper[index]) * 0.5 for index in range(3))
        size = tuple(max(upper[index] - lower[index], 0.25) for index in range(3))
        return center, size

    @staticmethod
    def _build_child_index(paths: list[str]) -> dict[str, list[str]]:
        children: dict[str, list[str]] = {}
        for path in paths:
            if path == "/":
                continue
            children.setdefault(parent_path(path), []).append(path)
        for rows in children.values():
            rows.sort()
        return children

    @staticmethod
    def _detect_root(paths: list[str], child_index: dict[str, list[str]]) -> str:
        if "/World" in paths:
            return "/World"
        roots = [path for path in paths if path.count("/") == 1 and path != "/"]
        content_roots = [root for root in sorted(roots) if root.rsplit("/", 1)[-1] not in VIEWER_ROOTS]
        if LOOKDEV_ASSET_ROOT in content_roots and len(content_roots) > 1:
            return "/"
        for root in content_roots:
            if child_index.get(root):
                return root
        if content_roots:
            return content_roots[0]
        return "/"

    def _classify(self, path: str) -> str:
        lower = Path(path).name.lower()
        if "camera" in lower:
            return "camera"
        if "light" in lower:
            return "light"
        if "mesh" in lower or "geom" in lower:
            return "geom"
        if lower in {"render", "viewerlighting"}:
            return "scope"
        return "xform"

    @staticmethod
    def _numbers(value: Any) -> list[float]:
        if isinstance(value, (int, float)):
            return [float(value)]
        if isinstance(value, str):
            return [float(match) for match in re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", value)]
        if isinstance(value, dict):
            numbers: list[float] = []
            for item in value.values():
                numbers.extend(StageQueryCache._numbers(item))
            return numbers
        if isinstance(value, (list, tuple)):
            numbers = []
            for item in value:
                numbers.extend(StageQueryCache._numbers(item))
            return numbers
        if hasattr(value, "tolist"):
            return StageQueryCache._numbers(value.tolist())
        return []

    @staticmethod
    def _is_viewer_path(path: str) -> bool:
        return path.count("/") > 0 and path.split("/", 2)[1] in VIEWER_ROOTS

    @staticmethod
    def _pxr_python() -> Path:
        runtime_python = Path(__file__).resolve().parents[1] / ".venv-win-runtime" / "Scripts" / "python.exe"
        if runtime_python.exists():
            return runtime_python
        return Path(sys.executable)
