from pathlib import Path
import tempfile
import unittest

from server.scene_loader import make_lookdev_composite


class SceneLoaderTests(unittest.TestCase):
    def test_composite_path_changes_when_asset_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            generated = root / "generated"
            studio = root / "studio.usda"
            first_asset = root / "first.usdc"
            second_asset = root / "second.usdc"
            studio.write_text("#usda 1.0\n", encoding="utf-8")
            first_asset.write_text("#usda 1.0\n", encoding="utf-8")
            second_asset.write_text("#usda 1.0\n", encoding="utf-8")

            first_composite = make_lookdev_composite(studio, first_asset, generated, 1920, 1080, {})
            second_composite = make_lookdev_composite(studio, second_asset, generated, 1920, 1080, {})

            self.assertNotEqual(first_composite, second_composite)

    def test_composite_path_is_deterministic_without_cache_bust_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            generated = root / "generated"
            studio = root / "studio.usda"
            asset = root / "asset.usdc"
            studio.write_text("#usda 1.0\n", encoding="utf-8")
            asset.write_text("#usda 1.0\n", encoding="utf-8")

            first_composite = make_lookdev_composite(studio, asset, generated, 1920, 1080, {})
            second_composite = make_lookdev_composite(studio, asset, generated, 1920, 1080, {})

            self.assertEqual(first_composite, second_composite)

    def test_composite_path_changes_with_cache_bust_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            generated = root / "generated"
            studio = root / "studio.usda"
            asset = root / "asset.usdc"
            studio.write_text("#usda 1.0\n", encoding="utf-8")
            asset.write_text("#usda 1.0\n", encoding="utf-8")

            first_composite = make_lookdev_composite(
                studio,
                asset,
                generated,
                1920,
                1080,
                {},
                cache_bust_token="mtime=1:size=10:seq=1",
            )
            second_composite = make_lookdev_composite(
                studio,
                asset,
                generated,
                1920,
                1080,
                {},
                cache_bust_token="mtime=2:size=20:seq=2",
            )

            self.assertNotEqual(first_composite, second_composite)

    def test_composite_can_reference_cache_busted_asset_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            generated = root / "generated"
            studio = root / "studio.usda"
            asset = root / "asset.usdc"
            snapshot = root / "._lookdev_reload_asset_token.usdc"
            studio.write_text("#usda 1.0\n", encoding="utf-8")
            asset.write_text("#usda 1.0\n", encoding="utf-8")
            snapshot.write_text("#usda 1.0\n", encoding="utf-8")

            composite = make_lookdev_composite(
                studio,
                asset,
                generated,
                1920,
                1080,
                {},
                cache_bust_token="mtime=2:size=20:seq=2",
                asset_reference_stage=snapshot,
            )

            self.assertIn("._lookdev_reload_asset_token.usdc", composite.read_text(encoding="utf-8"))
            self.assertIn("asset_", composite.name)


if __name__ == "__main__":
    unittest.main()
