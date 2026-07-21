from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PluginInfo:
    id: str
    name: str
    version: str
    enabled: bool
    category: str


class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, PluginInfo] = {}

    def register(self, plugin: PluginInfo) -> None:
        if plugin.id in self._plugins:
            raise ValueError(f"Plugin already registered: {plugin.id}")
        self._plugins[plugin.id] = plugin

    def list_plugins(self) -> list[PluginInfo]:
        return sorted(self._plugins.values(), key=lambda p: (p.category, p.name))

    def get(self, plugin_id: str) -> PluginInfo | None:
        return self._plugins.get(plugin_id)
