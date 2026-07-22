from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path
import zlib

from core.validation import PreviewValidationError, validate_preview_png


def chunk(kind: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(kind)
    crc = zlib.crc32(payload, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def make_png(width: int = 2, height: int = 2, color_type: int = 6,
             alpha_values: tuple[int, ...] = (255, 0, 0, 0)) -> bytes:
    channels = 4 if color_type == 6 else 3
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            alpha = alpha_values[y * width + x]
            rows.extend((30, 60, 90))
            if channels == 4:
                rows.append(alpha)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(rows)))
        + chunk(b"IEND", b"")
    )


class PreviewPngValidationTests(unittest.TestCase):
    def prepare(self, root: Path, png: bytes | None = None, **canvas_overrides):
        sprite = root / "Preview.png"
        sprite.write_bytes(png if png is not None else make_png())
        canvas = {
            "width": 2,
            "height": 2,
            "transparent": True,
            "colorMode": "RGBA",
            **canvas_overrides,
        }
        manifest = root / "preview_manifest.json"
        manifest.write_text(json.dumps({
            "schemaVersion": "1.1",
            "sprite": "Preview.png",
            "canvas": canvas,
        }))
        return manifest, sprite

    def test_validates_rgba_dimensions_alpha_and_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest, _ = self.prepare(Path(tmp))
            report = validate_preview_png(manifest)
            self.assertEqual((report.width, report.height), (2, 2))
            self.assertEqual(report.color_mode, "RGBA")
            self.assertEqual(report.bit_depth, 8)
            self.assertEqual(report.visible_pixels, 1)
            self.assertEqual(report.transparent_pixels, 3)
            self.assertEqual(report.alpha_bounds, (0, 0, 1, 1))
            self.assertEqual(report.coverage_ratio, 0.25)

    def test_rejects_dimension_mismatch_and_non_rgba(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, _ = self.prepare(root, width=3)
            with self.assertRaises(PreviewValidationError):
                validate_preview_png(manifest)
            manifest, _ = self.prepare(root, png=make_png(color_type=2))
            with self.assertRaises(PreviewValidationError):
                validate_preview_png(manifest)

    def test_rejects_corrupt_crc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest, sprite = self.prepare(Path(tmp))
            damaged = bytearray(sprite.read_bytes())
            damaged[-5] ^= 0x01
            sprite.write_bytes(damaged)
            with self.assertRaisesRegex(PreviewValidationError, "CRC mismatch"):
                validate_preview_png(manifest)

    def test_rejects_fully_opaque_and_fully_transparent_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, _ = self.prepare(root, png=make_png(alpha_values=(255,) * 4))
            with self.assertRaisesRegex(PreviewValidationError, "no transparent"):
                validate_preview_png(manifest)
            manifest, _ = self.prepare(root, png=make_png(alpha_values=(0,) * 4))
            with self.assertRaisesRegex(PreviewValidationError, "no visible"):
                validate_preview_png(manifest)

    def test_rejects_sprite_path_outside_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, _ = self.prepare(root)
            payload = json.loads(manifest.read_text())
            payload["sprite"] = "../outside.png"
            manifest.write_text(json.dumps(payload))
            with self.assertRaisesRegex(PreviewValidationError, "escapes"):
                validate_preview_png(manifest)

    def test_rejects_dimensions_above_render_limit_before_decompression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, _ = self.prepare(root, width=4097)
            with self.assertRaisesRegex(PreviewValidationError, "safe limits"):
                validate_preview_png(manifest)


if __name__ == "__main__":
    unittest.main()
