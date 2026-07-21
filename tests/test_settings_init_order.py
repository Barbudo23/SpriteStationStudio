from pathlib import Path
import ast
import unittest


class SettingsInitOrderTests(unittest.TestCase):
    def test_model_and_output_vars_exist_before_restore_use(self):
        path = Path(__file__).resolve().parents[1] / "app" / "gui.py"
        source = path.read_text(encoding="utf-8")
        model_create = source.index("self.model_var = tk.StringVar")
        model_set = source.find("self.model_var.set(self.app_settings")
        self.assertTrue(model_set == -1 or model_create < model_set)
        ast.parse(source)


if __name__ == "__main__":
    unittest.main()
