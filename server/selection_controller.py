from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SelectionController:
    selected_paths: list[str] = field(default_factory=list)
    pickable_paths: set[str] = field(default_factory=set)

    def clear(self) -> None:
        self.selected_paths = []

    def select(self, paths: list[str]) -> list[str]:
        self.selected_paths = [path for path in paths if path]
        return self.selected_paths

    def set_pickable(self, paths: list[str]) -> None:
        self.pickable_paths.update(path for path in paths if path)

    def payload(self) -> dict:
        return {"prims": self.selected_paths}

