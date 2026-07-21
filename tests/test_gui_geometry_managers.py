from pathlib import Path
import ast
import unittest


class GeometryManagerTests(unittest.TestCase):
    def test_topbar_does_not_mix_pack_and_grid(self):
        path = Path(__file__).resolve().parents[1] / "app" / "gui.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        method = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_build_topbar":
                method = node
                break
        self.assertIsNotNone(method)

        segment = ast.get_source_segment(source, method) or ""
        self.assertNotIn('.pack(', segment)
        self.assertIn('.grid(', segment)


if __name__ == "__main__":
    unittest.main()
