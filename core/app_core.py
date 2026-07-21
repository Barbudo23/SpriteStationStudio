from __future__ import annotations

from pathlib import Path

from core.events.event_bus import EventBus
from core.jobs.job_queue import JobQueue
from core.plugins.plugin_registry import PluginInfo, PluginRegistry
from core.project.project_manager import ProjectManager, AssetForgeProject
from core.database.asset_database import AssetDatabase


class AssetForgeCore:
    def __init__(self):
        self.events = EventBus()
        self.projects = ProjectManager()
        self.plugins = PluginRegistry()
        self.jobs = JobQueue(
            on_changed=lambda job: self.events.publish(
                "job.changed", job, source="core.jobs"
            )
        )
        self.current_project: AssetForgeProject | None = None
        self.asset_database: AssetDatabase | None = None
        self._register_builtin_plugins()

    def _register_builtin_plugins(self) -> None:
        for plugin in (
            PluginInfo("pseudo3d", "Pseudo3D Forge", "0.7.0", True, "production"),
            PluginInfo("blender_bridge", "Blender Bridge", "0.5.1", True, "bridge"),
            PluginInfo("unity_bridge", "Unity Bridge", "0.6.0", True, "bridge"),
            PluginInfo("unity_library", "Unity Asset Library", "0.6.0", True, "library"),
            PluginInfo("animation_sprites", "Animation Sprite Renderer", "0.1.0", True, "production"),
            PluginInfo("ai_center", "AI Center", "0.8.2-dev", True, "generation"),
        ):
            self.plugins.register(plugin)

    def activate_project(self, project: AssetForgeProject) -> None:
        self.current_project = project
        self.asset_database = AssetDatabase(project.database_path)
        self.events.publish("project.activated", project, source="core.project")

    def close(self) -> None:
        self.jobs.shutdown()
