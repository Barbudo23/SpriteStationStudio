from pathlib import Path
import tempfile
import unittest
from core.project.project_manager import ProjectManager, PROJECT_FOLDERS

class ProjectManagerTests(unittest.TestCase):
    def test_create_and_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ProjectManager()
            project = manager.create(Path(tmp), "Demo")
            for folder in PROJECT_FOLDERS:
                self.assertTrue((Path(project.root_path) / folder).is_dir())
            opened = manager.open(project.descriptor_path)
            self.assertEqual(opened.project_id, project.project_id)

if __name__ == "__main__":
    unittest.main()
