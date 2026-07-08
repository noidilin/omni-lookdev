from pathlib import Path
import tempfile
import unittest

import numpy as np

from server.config import LOOKDEV_ASSET_PRIM, ServerConfig
from server.runtime import LookdevRuntime
from server.scene_loader import STUDIO_CAMERA_XFORM


class FakeRenderer:
    def __init__(self) -> None:
        self.opened_paths: list[str] = []

    def open_usd(self, path: str) -> None:
        self.opened_paths.append(path)


class RuntimeReloadCameraTests(unittest.TestCase):
    def test_reload_asset_resets_to_studio_camera_instead_of_preserving_current_view(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            studio = root / "lookdev-studio.usdc"
            asset_root = root / "assets"
            generated = root / "generated"
            settings = root / "viewer-settings.json"
            asset = asset_root / "asset.usdc"
            asset_root.mkdir()
            studio.write_text("#usda 1.0\n", encoding="utf-8")
            asset.write_text("#usda 1.0\n", encoding="utf-8")
            runtime = LookdevRuntime(
                ServerConfig(
                    studio_stage=studio,
                    asset_root=asset_root,
                    settings_path=settings,
                    generated_dir=generated,
                )
            )
            runtime.renderer = FakeRenderer()
            runtime.current_asset_path = asset

            def refresh_queries(_asset_path, _composite_path=None, queries=None, *, stream_warmup_frames=True):
                queries.paths = [LOOKDEV_ASSET_PRIM]
                queries.root_prim_path = "/"
                return True

            runtime._refresh_queries_after_load = refresh_queries
            runtime.camera.fit_bounds((100.0, 100.0, 100.0), (1.0, 1.0, 1.0))

            runtime._load_stage(asset, reload_current=True)

            np.testing.assert_allclose(runtime.camera.get_camera_xform(), np.asarray(STUDIO_CAMERA_XFORM), atol=1e-10)
            self.assertGreater(len(runtime.renderer.opened_paths), 0)


if __name__ == "__main__":
    unittest.main()
