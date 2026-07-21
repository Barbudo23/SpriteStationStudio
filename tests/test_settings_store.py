from pathlib import Path
import json
import tempfile
import unittest

from app.settings_store import AppSettings, SettingsStore


class SettingsStoreTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            store = SettingsStore(path)
            expected = AppSettings(
                blender_executable="C:/Blender/blender.exe",
                unity_executable="C:/Unity/Unity.exe",
                last_model_path="C:/Models/Soldier.fbx",
                last_output_path="C:/Output",
                last_unity_project="C:/Projects/Game",
            )
            store.save(expected)
            self.assertEqual(store.load(), expected)

    def test_corrupt_settings_fall_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(SettingsStore(path).load(), AppSettings())

    def test_unknown_fields_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text(
                json.dumps({"unity_executable": "Unity.exe", "future": 123}),
                encoding="utf-8",
            )
            loaded = SettingsStore(path).load()
            self.assertEqual(loaded.unity_executable, "Unity.exe")


if __name__ == "__main__":
    unittest.main()
