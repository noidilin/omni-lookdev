from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


DEBUG_AOVS: tuple[dict[str, str], ...] = (
    {"name": "LdrColor", "label": "Beauty"},
    {"name": "NormalSD", "label": "Normals"},
    {"name": "DepthSD", "label": "Depth"},
)

DEBUG_AOV_NAMES = tuple(option["name"] for option in DEBUG_AOVS)


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
        label="Debug AOV",
        control="segmented",
        applies_at="immediate",
        apply_path="server frame conversion selects and colorizes active render var",
        validated=True,
    ),
}


def capabilities_payload() -> list[dict[str, Any]]:
    return [
        asdict(capability)
        for capability in CAPABILITIES.values()
        if capability.validated and capability.applies_at != "unsupported"
    ]


def coerce_setting(key: str, value: Any) -> Any:
    if key == "aov":
        requested = str(value or "LdrColor")
        return requested if requested in DEBUG_AOV_NAMES else requested
    return value


def aov_options_payload() -> list[dict[str, str]]:
    return [dict(option) for option in DEBUG_AOVS]
