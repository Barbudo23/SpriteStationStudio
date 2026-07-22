from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import struct
import zlib


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_PNG_BYTES = 128 * 1024 * 1024
MAX_DIMENSION = 4096
MAX_PIXELS = MAX_DIMENSION * MAX_DIMENSION


class PreviewValidationError(ValueError):
    pass


@dataclass(frozen=True)
class PreviewPngReport:
    manifest_path: Path
    sprite_path: Path
    width: int
    height: int
    color_mode: str
    bit_depth: int
    visible_pixels: int
    transparent_pixels: int
    alpha_bounds: tuple[int, int, int, int]

    @property
    def total_pixels(self) -> int:
        return self.width * self.height

    @property
    def coverage_ratio(self) -> float:
        return self.visible_pixels / self.total_pixels


def validate_preview_png(manifest_path: Path) -> PreviewPngReport:
    manifest_path = manifest_path.expanduser().resolve()
    if not manifest_path.is_file():
        raise PreviewValidationError(f"Preview manifest not found: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreviewValidationError(f"Cannot read Preview manifest: {exc}") from exc
    if manifest.get("schemaVersion") != "1.1":
        raise PreviewValidationError("Preview manifest must use schemaVersion 1.1.")

    canvas = manifest.get("canvas")
    if not isinstance(canvas, dict):
        raise PreviewValidationError("Preview manifest has no canvas object.")
    try:
        expected_width = int(canvas["width"])
        expected_height = int(canvas["height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PreviewValidationError("Preview canvas dimensions are invalid.") from exc
    if (
        expected_width < 1
        or expected_height < 1
        or expected_width > MAX_DIMENSION
        or expected_height > MAX_DIMENSION
        or expected_width * expected_height > MAX_PIXELS
    ):
        raise PreviewValidationError("Preview canvas dimensions are outside safe limits.")
    if canvas.get("transparent") is not True or canvas.get("colorMode") != "RGBA":
        raise PreviewValidationError("Preview canvas must declare transparent RGBA.")

    sprite_value = manifest.get("sprite")
    if not isinstance(sprite_value, str) or not sprite_value.strip():
        raise PreviewValidationError("Preview manifest does not reference a sprite.")
    package_root = manifest_path.parent.resolve()
    sprite_path = (package_root / sprite_value).resolve()
    try:
        sprite_path.relative_to(package_root)
    except ValueError as exc:
        raise PreviewValidationError("Preview sprite path escapes the package.") from exc
    if not sprite_path.is_file():
        raise PreviewValidationError(f"Preview sprite not found: {sprite_path}")

    width, height, bit_depth, rgba = _decode_rgba_png(sprite_path)
    if (width, height) != (expected_width, expected_height):
        raise PreviewValidationError(
            "PNG dimensions do not match manifest canvas: "
            f"{width}x{height} != {expected_width}x{expected_height}."
        )

    alpha = rgba[3::4]
    visible_indices = [index for index, value in enumerate(alpha) if value > 0]
    transparent_pixels = sum(value < 255 for value in alpha)
    if not visible_indices:
        raise PreviewValidationError("Preview PNG contains no visible pixels.")
    if transparent_pixels == 0:
        raise PreviewValidationError("Preview PNG contains no transparent pixels.")
    xs = [index % width for index in visible_indices]
    ys = [index // width for index in visible_indices]

    return PreviewPngReport(
        manifest_path=manifest_path,
        sprite_path=sprite_path,
        width=width,
        height=height,
        color_mode="RGBA",
        bit_depth=bit_depth,
        visible_pixels=len(visible_indices),
        transparent_pixels=transparent_pixels,
        alpha_bounds=(min(xs), min(ys), max(xs) + 1, max(ys) + 1),
    )


def _decode_rgba_png(path: Path) -> tuple[int, int, int, bytes]:
    if path.stat().st_size > MAX_PNG_BYTES:
        raise PreviewValidationError("Preview PNG exceeds the safe file-size limit.")
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise PreviewValidationError("Preview file is not a PNG.")
    offset = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = None
    compressed = bytearray()
    saw_ihdr = False
    saw_iend = False

    while offset < len(data):
        if offset + 12 > len(data):
            raise PreviewValidationError("PNG contains a truncated chunk header.")
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        chunk_end = offset + 12 + length
        if chunk_end > len(data):
            raise PreviewValidationError("PNG contains a truncated chunk payload.")
        payload = data[offset + 8:offset + 8 + length]
        stored_crc = struct.unpack(">I", data[offset + 8 + length:chunk_end])[0]
        actual_crc = zlib.crc32(chunk_type)
        actual_crc = zlib.crc32(payload, actual_crc) & 0xFFFFFFFF
        if stored_crc != actual_crc:
            raise PreviewValidationError(
                f"PNG chunk CRC mismatch: {chunk_type.decode('ascii', errors='replace')}"
            )

        if chunk_type == b"IHDR":
            if saw_ihdr or offset != len(PNG_SIGNATURE) or length != 13:
                raise PreviewValidationError("PNG has an invalid IHDR chunk.")
            width, height, bit_depth, color_type, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", payload)
            )
            saw_ihdr = True
            if (
                width < 1
                or height < 1
                or width > MAX_DIMENSION
                or height > MAX_DIMENSION
                or width * height > MAX_PIXELS
            ):
                raise PreviewValidationError("PNG dimensions are outside safe limits.")
            if bit_depth != 8 or color_type != 6:
                raise PreviewValidationError("Preview PNG must be 8-bit RGBA (color type 6).")
            if compression != 0 or filtering != 0 or interlace != 0:
                raise PreviewValidationError(
                    "Preview PNG must use standard compression/filtering and no interlace."
                )
        elif chunk_type == b"IDAT":
            if not saw_ihdr:
                raise PreviewValidationError("PNG IDAT appears before IHDR.")
            compressed.extend(payload)
        elif chunk_type == b"IEND":
            if length != 0:
                raise PreviewValidationError("PNG IEND chunk must be empty.")
            saw_iend = True
            offset = chunk_end
            break
        offset = chunk_end

    if not saw_ihdr or not compressed or not saw_iend or offset != len(data):
        raise PreviewValidationError("PNG is missing required chunks or has trailing data.")
    assert width is not None and height is not None and bit_depth is not None
    try:
        scanlines = zlib.decompress(bytes(compressed))
    except zlib.error as exc:
        raise PreviewValidationError(f"PNG IDAT decompression failed: {exc}") from exc
    stride = width * 4
    expected_size = height * (stride + 1)
    if len(scanlines) != expected_size:
        raise PreviewValidationError("PNG decompressed size does not match IHDR dimensions.")
    return width, height, bit_depth, _unfilter(scanlines, width, height)


def decode_rgba_png(path: Path) -> tuple[int, int, bytes]:
    """Decode a validated, non-interlaced 8-bit RGBA PNG."""
    width, height, _, rgba = _decode_rgba_png(path.expanduser().resolve())
    return width, height, rgba


def encode_rgba_png(width: int, height: int, rgba: bytes) -> bytes:
    """Encode RGBA pixels with deterministic filter-0 scanlines."""
    if width < 1 or height < 1 or width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise PreviewValidationError("PNG dimensions are outside safe limits.")
    if width * height > MAX_PIXELS or len(rgba) != width * height * 4:
        raise PreviewValidationError("RGBA payload does not match PNG dimensions.")
    scanlines = bytearray()
    stride = width * 4
    for row in range(height):
        scanlines.append(0)
        start = row * stride
        scanlines.extend(rgba[start:start + stride])

    def chunk(kind: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(payload, zlib.crc32(kind)) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        PNG_SIGNATURE
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(scanlines), level=9))
        + chunk(b"IEND", b"")
    )


def _unfilter(scanlines: bytes, width: int, height: int) -> bytes:
    stride = width * 4
    previous = bytearray(stride)
    decoded = bytearray()
    offset = 0
    for _ in range(height):
        filter_type = scanlines[offset]
        raw = scanlines[offset + 1:offset + 1 + stride]
        offset += stride + 1
        row = bytearray(stride)
        for index, value in enumerate(raw):
            left = row[index - 4] if index >= 4 else 0
            above = previous[index]
            upper_left = previous[index - 4] if index >= 4 else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = above
            elif filter_type == 3:
                predictor = (left + above) // 2
            elif filter_type == 4:
                predictor = _paeth(left, above, upper_left)
            else:
                raise PreviewValidationError(f"Unsupported PNG filter type: {filter_type}")
            row[index] = (value + predictor) & 0xFF
        decoded.extend(row)
        previous = row
    return bytes(decoded)


def _paeth(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    distance_left = abs(estimate - left)
    distance_above = abs(estimate - above)
    distance_upper_left = abs(estimate - upper_left)
    if distance_left <= distance_above and distance_left <= distance_upper_left:
        return left
    if distance_above <= distance_upper_left:
        return above
    return upper_left
