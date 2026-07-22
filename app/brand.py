from pathlib import Path


PRODUCT_NAME = "Sprite Station Studio"
PRODUCT_SHORT_NAME = "SSS"
PRODUCT_SLUG = "sprite-station-studio"
CONFIG_DIR_NAME = ".sprite_station_studio"
LEGACY_CONFIG_DIR_NAME = ".assetforge"
UNITY_IMPORTS_DIR = "SpriteStationImports"
LEGACY_UNITY_IMPORTS_DIR = "AssetForgeImports"


def config_path(filename: str) -> Path:
    return Path.home() / CONFIG_DIR_NAME / filename


def legacy_config_path(filename: str) -> Path:
    return Path.home() / LEGACY_CONFIG_DIR_NAME / filename
