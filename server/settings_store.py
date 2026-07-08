from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS: dict[str, Any] = {
    "render": {
        "aov": "LdrColor",
        "samples_per_pixel": 64,
        "denoiser": True,
        "resolution": {"width": 1920, "height": 1080},
        "viewer_lighting": {
            "enabled": False,
            "fallback": False,
            "key_intensity": 500.0,
            "fill_intensity": 80.0,
            "environment_intensity": 1.0,
        },
    }
}


class SettingsStore:
    def __init__(self, path: Path):
        self.path = path
        self.data = self.load()

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return json.loads(json.dumps(DEFAULT_SETTINGS))
        with self.path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        merged = json.loads(json.dumps(DEFAULT_SETTINGS))
        self._deep_update(merged, loaded)
        return merged

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(self.data, handle, indent=2)
            handle.write("\n")

    def render_settings(self) -> dict[str, Any]:
        return self.data.setdefault("render", {})

    @staticmethod
    def _deep_update(target: dict[str, Any], source: dict[str, Any]) -> None:
        for key, value in source.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                SettingsStore._deep_update(target[key], value)
            else:
                target[key] = value
