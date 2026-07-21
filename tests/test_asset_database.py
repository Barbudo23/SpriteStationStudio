from pathlib import Path
import tempfile
import unittest
from core.database.asset_database import AssetDatabase

class AssetDatabaseTests(unittest.TestCase):
    def test_upsert_and_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / "Soldier.fbx"
            file.write_bytes(b"model")
            db = AssetDatabase(root / "assets.sqlite3")
            db.upsert_file("guid1", "Soldier", "Model", file, "Assets/Soldier.fbx")
            rows = db.list_assets("Soldier", "Model")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].guid, "guid1")

if __name__ == "__main__":
    unittest.main()
