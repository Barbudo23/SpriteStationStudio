from pathlib import Path
import tempfile
import unittest

from app.unity_asset_library import UnityAssetLibrary


class UnityAssetLibraryTests(unittest.TestCase):
    def create_project(self, root: Path) -> Path:
        project = root / "TestProject"
        (project / "Assets/Characters").mkdir(parents=True)
        (project / "ProjectSettings").mkdir(parents=True)
        (project / "ProjectSettings/ProjectVersion.txt").write_text(
            "m_EditorVersion: 6000.0.42f1\n",
            encoding="utf-8",
        )
        return project

    def test_detects_unity_project_and_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self.create_project(Path(tmp))
            self.assertTrue(UnityAssetLibrary.is_unity_project(project))
            self.assertEqual(
                UnityAssetLibrary.read_unity_version(project),
                "6000.0.42f1",
            )

    def test_scans_models_and_reads_guid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self.create_project(root)
            model = project / "Assets/Characters/Soldier.fbx"
            model.write_bytes(b"fbx")
            (project / "Assets/Characters/Soldier.fbx.meta").write_text(
                "fileFormatVersion: 2\nguid: abcdef1234567890\n",
                encoding="utf-8",
            )

            library = UnityAssetLibrary(root / "cache")
            records = library.scan_project(project)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].asset_type, "Model")
            self.assertEqual(records[0].guid, "abcdef1234567890")
            self.assertEqual(records[0].unity_path, "Assets/Characters/Soldier.fbx")

    def test_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self.create_project(root)
            (project / "Assets/Characters/Soldier.obj").write_text("o soldier")

            library = UnityAssetLibrary(root / "cache")
            original = library.scan_project(project)
            restored = library.read_cache(project)

            self.assertEqual(original, restored)

    def test_filter_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = self.create_project(root)
            (project / "Assets/Characters/Soldier.fbx").write_bytes(b"x")
            (project / "Assets/Characters/Enemy.png").write_bytes(b"x")

            library = UnityAssetLibrary(root / "cache")
            records = library.scan_project(project)

            models = library.filter_records(records, "sold", "Model")
            self.assertEqual(len(models), 1)
            self.assertEqual(models[0].name, "Soldier")


if __name__ == "__main__":
    unittest.main()
