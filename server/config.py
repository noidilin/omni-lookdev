from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
STUDIO_STAGE = WORKSPACE_ROOT / "studio" / "lookdev-studio.usdc"
ASSET_ROOT = WORKSPACE_ROOT / "assets"
DATA_DIR = WORKSPACE_ROOT / "data"
GENERATED_DIR = DATA_DIR / "generated"
SETTINGS_PATH = DATA_DIR / "viewer-settings.json"

OV_CAMERA_PRIM = "/OVCamera"
STUDIO_CAMERA_PRIM = "/root/medium/Camera"
OV_RENDER_PRODUCT = "/Render/OVServer/ViewportTexture0"
LOOKDEV_ASSET_PRIM = "/LookdevAsset"

DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
DEFAULT_FPS = 60
DEFAULT_SIGNALING_PORT = 49100
DEFAULT_HEALTH_PORT = 8081


@dataclass(frozen=True)
class ServerConfig:
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    fps: int = DEFAULT_FPS
    signaling_port: int = DEFAULT_SIGNALING_PORT
    health_port: int = DEFAULT_HEALTH_PORT
    public_ip: str = "127.0.0.1"
    studio_stage: Path = STUDIO_STAGE
    asset_root: Path = ASSET_ROOT
    settings_path: Path = SETTINGS_PATH
    generated_dir: Path = GENERATED_DIR

    @property
    def stream_resolution(self) -> tuple[int, int]:
        return self.width, self.height
