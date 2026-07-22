from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ModuleDescriptor:
    id: str
    display_name: str
    icon: str
    description: str
    enabled: bool = True


class ModuleRegistry:
    def __init__(self) -> None:
        self._modules: list[ModuleDescriptor] = []

    def register(self, module: ModuleDescriptor) -> None:
        if any(existing.id == module.id for existing in self._modules):
            raise ValueError(f"Module already registered: {module.id}")
        self._modules.append(module)

    def all(self) -> tuple[ModuleDescriptor, ...]:
        return tuple(self._modules)


def create_default_registry() -> ModuleRegistry:
    registry = ModuleRegistry()
    registry.register(ModuleDescriptor(
        "dashboard", "Dashboard", "⌂", "Проекты, последние задачи и быстрый запуск."
    ))
    registry.register(ModuleDescriptor(
        "pseudo3d_forge", "Pseudo3D Forge", "◈",
        "3D-модель → PNG, направления, анимации и sprite sheet."
    ))
    registry.register(ModuleDescriptor(
        "ai_center", "AI Center", "AI",
        "Генерация изображений через OpenAI API, Codex Bridge или CloseAI API."
    ))
    registry.register(ModuleDescriptor(
        "motion_lab", "MotionLab", "▶",
        "Экспериментальные циклы, GIF-превью и движение.", enabled=False
    ))
    registry.register(ModuleDescriptor(
        "camera_lab", "CameraLab", "◉",
        "Профили камеры и визуальная настройка ракурса.", enabled=False
    ))
    registry.register(ModuleDescriptor(
        "sprite_builder", "SpriteBuilder", "▦",
        "Approved Static Sprite workflow, audit и Unity preview package."
    ))
    registry.register(ModuleDescriptor(
        "atlas_builder", "AtlasBuilder", "▤",
        "Сборка и оптимизация атласов.", enabled=False
    ))
    return registry
