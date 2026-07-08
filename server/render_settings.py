from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RenderSettingCapability:
    key: str
    label: str
    control: str
    applies_at: str
    apply_path: str
    validated: bool
    min: float | None = None
    max: float | None = None
    step: float | None = None


CAPABILITIES: dict[str, RenderSettingCapability] = {
    "aov": RenderSettingCapability(
        key="aov",
        label="AOV",
        control="select",
        applies_at="immediate",
        apply_path="server frame conversion selects active render var",
        validated=True,
    ),
    "samples_per_pixel": RenderSettingCapability(
        key="samples_per_pixel",
        label="Samples",
        control="slider",
        applies_at="reload_required",
        apply_path="viewer composite RenderProduct RTX attributes",
        validated=True,
        min=1,
        max=4096,
        step=1,
    ),
    "denoiser": RenderSettingCapability(
        key="denoiser",
        label="Denoiser",
        control="switch",
        applies_at="reload_required",
        apply_path="viewer composite RenderProduct RTX denoiser attributes",
        validated=True,
    ),
    "resolution": RenderSettingCapability(
        key="resolution",
        label="Stream Resolution",
        control="select",
        applies_at="reconnect_required",
        apply_path="fixed ovstream ServerConfig and RenderProduct resolution",
        validated=True,
    ),
    "viewer_lighting": RenderSettingCapability(
        key="viewer_lighting",
        label="Viewer Lighting",
        control="group",
        applies_at="unsupported",
        apply_path="studio-authored lookdev lighting is used by default",
        validated=False,
    ),
}


def capabilities_payload() -> list[dict[str, Any]]:
    return [
        asdict(capability)
        for capability in CAPABILITIES.values()
        if capability.validated and capability.applies_at != "unsupported"
    ]


def coerce_setting(key: str, value: Any) -> Any:
    if key == "samples_per_pixel":
        return int(max(1, min(4096, int(value))))
    if key == "denoiser":
        return bool(value)
    if key == "aov":
        return str(value or "LdrColor")
    if key == "resolution":
        width = int(value.get("width", 1920))
        height = int(value.get("height", 1080))
        allowed = {(1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)}
        if (width, height) not in allowed:
            width, height = 1920, 1080
        return {"width": width, "height": height}
    if key == "viewer_lighting":
        return {
            "enabled": bool(value.get("enabled", False)),
            "fallback": bool(value.get("fallback", False)),
            "key_intensity": float(value.get("key_intensity", 500.0)),
            "fill_intensity": float(value.get("fill_intensity", 80.0)),
            "environment_intensity": float(value.get("environment_intensity", 1.0)),
        }
    return value
