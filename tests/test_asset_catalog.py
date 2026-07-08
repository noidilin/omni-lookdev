from pathlib import Path
import tempfile
import unittest

from server.asset_catalog import AssetCatalog


class AssetCatalogTests(unittest.TestCase):
    def test_list_assets_excludes_reload_snapshots_and_hidden_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "visible.usdc").write_text("#usda 1.0\n", encoding="utf-8")
            (root / "visible_1.usdc").write_text("#usda 1.0\n", encoding="utf-8")
            (root / "._lookdev_reload_visible_digest_token.usdc").write_text("#usda 1.0\n", encoding="utf-8")
            hidden_dir = root / ".hidden"
            hidden_dir.mkdir()
            (hidden_dir / "nested.usda").write_text("#usda 1.0\n", encoding="utf-8")

            rows = AssetCatalog(root).list_assets()

            self.assertEqual(
                [row["path"] for row in rows],
                ["visible.usdc", "visible_1.usdc"],
            )

    def test_first_asset_skips_internal_reload_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "._lookdev_reload_visible_digest_token.usdc").write_text("#usda 1.0\n", encoding="utf-8")
            expected = root / "visible.usdc"
            expected.write_text("#usda 1.0\n", encoding="utf-8")

            self.assertEqual(AssetCatalog(root).first_asset(), expected.resolve())


if __name__ == "__main__":
    unittest.main()
