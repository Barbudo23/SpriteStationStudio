import unittest
from core.plugins.plugin_registry import PluginInfo, PluginRegistry

class PluginRegistryTests(unittest.TestCase):
    def test_register(self):
        registry = PluginRegistry()
        registry.register(PluginInfo("x", "X", "1.0", True, "test"))
        self.assertEqual(registry.get("x").name, "X")

if __name__ == "__main__":
    unittest.main()
