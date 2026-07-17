"""AssetForge YAML configuration loader."""
from pathlib import Path
from typing import Any
import yaml

class ConfigLoader:
    REQUIRED_CORE = ("MPI.yaml", "Manifest.yaml", "CameraLibrary.yaml", "QA_Profile.yaml")

    def __init__(self, root: Path):
        self.root = Path(root)

    def load(self, filename: str) -> dict[str, Any]:
        path = self.root / filename
        if not path.is_file():
            raise FileNotFoundError(f"Missing config: {path}")
        with path.open("r", encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
        if not isinstance(data, dict):
            raise ValueError(f"Config must contain a YAML mapping: {path}")
        return data

    def load_all(self) -> dict[str, dict[str, Any]]:
        self.validate()
        return {name: self.load(name) for name in self.REQUIRED_CORE}

    def validate(self) -> None:
        missing = [name for name in self.REQUIRED_CORE if not (self.root / name).is_file()]
        if missing:
            raise RuntimeError("Missing configuration files: " + ", ".join(missing))
