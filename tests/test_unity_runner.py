from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

from app.unity_runner import UnityRunner, UnityBridgeError


class UnityRunnerTests(unittest.TestCase):
    def test_validate_executable_rejects_hub(self):
        with tempfile.TemporaryDirectory() as tmp:
            hub = Path(tmp) / "Unity Hub.exe"
            hub.write_text("")
            with self.assertRaises(UnityBridgeError):
                UnityRunner.validate_executable(hub)

    def test_query_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            unity = Path(tmp) / "Unity.exe"
            unity.write_text("")
            fake = Mock(return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="6000.0.42f1", stderr=""
            ))
            runner = UnityRunner(fake)
            self.assertEqual(runner.query_version(unity), "6000.0.42f1")

    def test_execute_uses_batchmode_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unity = root / "Unity.exe"
            unity.write_text("")
            project = root / "project"
            project.mkdir()
            report = root / "report.json"
            command = root / "command.json"
            command.write_text(json.dumps({"reportPath": str(report)}))
            fake = Mock(return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            ))
            runner = UnityRunner(fake)
            result = runner.execute(
                unity, project, "AssetForgeUnityBridge.Execute",
                command, root / "unity.log"
            )
            args = fake.call_args.args[0]
            self.assertIn("-batchmode", args)
            self.assertIn("-executeMethod", args)
            self.assertEqual(result.report_path, report)


    def test_find_installations_returns_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            older = root / "2022.3.10f1" / "Editor" / "Unity.exe"
            newer = root / "6000.0.42f1" / "Editor" / "Unity.exe"
            older.parent.mkdir(parents=True)
            newer.parent.mkdir(parents=True)
            older.write_text("")
            newer.write_text("")

            runner = UnityRunner()
            runner.common_install_roots = lambda: (root,)
            found = runner.find_installations()

            self.assertEqual(found[0], newer.resolve())
            self.assertIn(older.resolve(), found)

    def test_find_working_installations_skips_broken_editor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            broken = root / "6000.0.50f1" / "Editor" / "Unity.exe"
            good = root / "6000.0.42f1" / "Editor" / "Unity.exe"
            broken.parent.mkdir(parents=True)
            good.parent.mkdir(parents=True)
            broken.write_text("")
            good.write_text("")

            runner = UnityRunner()
            runner.find_installations = lambda: [broken, good]

            def fake_query(path, timeout=90):
                if path == broken:
                    raise UnityBridgeError("broken editor")
                return "6000.0.42f1"

            runner.query_version = fake_query
            working = runner.find_working_installations()

            self.assertEqual(len(working), 1)
            self.assertEqual(working[0].executable, good)


if __name__ == "__main__":
    unittest.main()
