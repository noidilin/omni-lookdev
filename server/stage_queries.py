from __future__ import annotations

from pathlib import Path
from typing import Any


VIEWER_ROOTS = {"Render", "ViewerLighting"}


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

    def refresh_from_renderer(self, renderer) -> None:
        try:
            result = renderer.query_prims(attribute_filter_mode=0)
        except TypeError:
            result = renderer.query_prims()
        self.attrs = dict(result)
        self.paths = sorted(self.attrs.keys())
        self.child_index = self._build_child_index(self.paths)
        self.root_prim_path = self._detect_root(self.paths)

    def get_children(self, prim_path: str) -> list[dict[str, Any]]:
        rows = []
        for child in self.child_index.get(prim_path or self.root_prim_path, []):
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
    def _detect_root(paths: list[str]) -> str:
        if "/World" in paths:
            return "/World"
        roots = [path for path in paths if path.count("/") == 1 and path != "/"]
        for root in sorted(roots):
            if root.rsplit("/", 1)[-1] not in VIEWER_ROOTS:
                return root
        return roots[0] if roots else "/"

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

