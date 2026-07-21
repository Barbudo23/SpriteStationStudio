from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import sqlite3
import time


@dataclass(frozen=True)
class AssetRow:
    id: int
    guid: str
    name: str
    asset_type: str
    source_path: str
    project_path: str
    status: str
    hash_sha256: str
    created_utc: float
    modified_utc: float


class AssetDatabase:
    def __init__(self, path: Path):
        self.path = path.expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guid TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    project_path TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'ready',
                    hash_sha256 TEXT NOT NULL,
                    created_utc REAL NOT NULL,
                    modified_utc REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_assets_name ON assets(name);
                CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);
                CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);
            """)

    @staticmethod
    def hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def upsert_file(
        self,
        guid: str,
        name: str,
        asset_type: str,
        source_path: Path,
        project_path: str,
        status: str = "ready",
    ) -> None:
        source_path = source_path.expanduser().resolve()
        now = time.time()
        file_hash = self.hash_file(source_path) if source_path.is_file() else ""
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO assets (
                    guid, name, asset_type, source_path, project_path,
                    status, hash_sha256, created_utc, modified_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guid) DO UPDATE SET
                    name=excluded.name,
                    asset_type=excluded.asset_type,
                    source_path=excluded.source_path,
                    project_path=excluded.project_path,
                    status=excluded.status,
                    hash_sha256=excluded.hash_sha256,
                    modified_utc=excluded.modified_utc
            """, (
                guid, name, asset_type, str(source_path), project_path,
                status, file_hash, now, now,
            ))

    def list_assets(self, query: str = "", asset_type: str | None = None) -> list[AssetRow]:
        sql = "SELECT * FROM assets WHERE 1=1"
        args: list[object] = []
        if query:
            sql += " AND (name LIKE ? OR source_path LIKE ?)"
            value = f"%{query}%"
            args.extend([value, value])
        if asset_type:
            sql += " AND asset_type = ?"
            args.append(asset_type)
        sql += " ORDER BY modified_utc DESC, name COLLATE NOCASE"
        with self.connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [AssetRow(**dict(row)) for row in rows]
