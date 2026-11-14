"""Generate realistic synthetic SAR overlays for the GERD timeline.

Until real GeoTIFF exports from ASF Vertex are dropped into raw_tiffs/ and
converted with clean.py, this script produces dark-water / bright-terrain PNGs
that let the frontend 3D terrain draping work immediately.

Usage:
    python scripts/generate_mock_overlays.py [--force] [--size 1200]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "overlays"

# Must match app/services/gerd_data.py and the frontend draping contract.
WEST, SOUTH, EAST, NORTH = 34.8500, 10.8500, 35.4500, 11.4500
CENTER_LAT, CENTER_LON = 11.215, 35.093

SCENES = [
    {"filename": "gerd_2019_pre.png", "year": 2019, "fill": 0.06, "dam_width": 2},
    {"filename": "gerd_2021_fill2.png", "year": 2021, "fill": 0.34, "dam_width": 4},
    {"filename": "gerd_2023_fill4.png", "year": 2023, "fill": 0.68, "dam_width": 6},
    {"filename": "gerd_2025_full.png", "year": 2025, "fill": 1.0, "dam_width": 8},
]


def _smooth_noise(
    width: int, height: int, rng: np.random.Generator, cell: int
) -> np.ndarray:
    """Return smooth 0..1 noise by upsampling a coarse random grid."""

    grid_h = max(2, height // cell)
    grid_w = max(2, width // cell)
    coarse = rng.random((grid_h, grid_w)).astype(np.float32)
    image = Image.fromarray((coarse * 255).astype(np.uint8), mode="L")
    image = image.resize((width, height), Image.Resampling.BICUBIC)
    return np.asarray(image, dtype=np.float32) / 255.0


def _terrain(width: int, height: int, rng: np.random.Generator) -> np.ndarray:
    """Build multi-scale terrain backscatter (rough surfaces return energy)."""

    noise = (
        0.50 * _smooth_noise(width, height, rng, 24)
        + 0.30 * _smooth_noise(width, height, rng, 8)
        + 0.20 * _smooth_noise(width, height, rng, 3)
    )
    noise = (noise - noise.min()) / (float(np.ptp(noise)) or 1.0)

    x = np.linspace(0.0, 1.0, width, dtype=np.float32)[None, :]
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
    ridges = 0.5 + 0.5 * np.sin(18.0 * x + 11.0 * y + 3.0 * noise)
    relief = 0.6 * noise + 0.4 * ridges

    return np.clip(55.0 + 165.0 * relief, 0.0, 255.0)


def _lonlat_to_pixel(
    lon: float, lat: float, width: int, height: int
) -> tuple[float, float]:
    x = (lon - WEST) / (EAST - WEST) * width
    y = (NORTH - lat) / (NORTH - SOUTH) * height
    return x, y


def _reservoir_polygon(
    center: tuple[float, float],
    length: float,
    half_width: float,
    rng: np.random.Generator,
) -> list[tuple[float, float]]:
    """Create an irregular, elongated reservoir outline flowing southward."""

    cx, cy = center
    angle = np.deg2rad(104.0)
    axis = np.array([np.cos(angle), np.sin(angle)], dtype=np.float32)
    perp = np.array([-axis[1], axis[0]], dtype=np.float32)

    points: list[tuple[float, float]] = []
    steps = 40
    for side in (1, -1):
        for i in range(steps + 1):
            t = -0.5 + i / steps
            along = t * length
            profile = np.sqrt(max(0.0, 1.0 - (2.0 * t) ** 2))
            wobble = 1.0 + 0.18 * np.sin(7.0 * np.pi * t + side)
            width_here = half_width * (0.22 + 0.78 * profile) * wobble
            width_here *= 1.0 + 0.05 * rng.standard_normal()
            point = (
                cx + axis[0] * along + perp[0] * width_here * side,
                cy + axis[1] * along + perp[1] * width_here * side,
            )
            points.append(point)
    return points


def _build_overlay(
    width: int, height: int, year: int, fill: float, dam_width: int
) -> Image.Image:
    rng = np.random.default_rng(year)
    background = _terrain(width, height, rng)

    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)

    center = _lonlat_to_pixel(CENTER_LON, CENTER_LAT, width, height)
    max_length = 0.46 * height
    max_half_width = 0.055 * width

    length = max_length * (0.12 + 0.88 * fill)
    half_width = max_half_width * (0.18 + 0.82 * fill)

    if fill <= 0.1:
        river = [(width * 0.60, 0.0), (width * 0.55, height * 0.25), center,
                 (width * 0.47, height * 0.72), (width * 0.44, height)]
        draw.line(river, fill=255, width=max(3, int(width * 0.008)), joint="curve")
    else:
        polygon = _reservoir_polygon(center, length, half_width, rng)
        draw.polygon(polygon, fill=255)
        tributary = [
            (center[0] - width * 0.05, center[1] - height * 0.02),
            (center[0] - width * 0.12, center[1] + height * 0.12),
            (center[0] - width * 0.16, center[1] + height * 0.24),
        ]
        draw.line(tributary, fill=255, width=max(2, int(width * 0.006 * fill)),
                  joint="curve")
        if fill > 0.5:
            bay = [
                (center[0] + width * 0.01, center[1] - height * 0.04),
                (center[0] + width * 0.10, center[1] + height * 0.02),
                (center[0] + width * 0.13, center[1] + height * 0.10),
                (center[0] + width * 0.05, center[1] + height * 0.12),
            ]
            draw.polygon(bay, fill=255)

    mask = mask.filter(ImageFilter.GaussianBlur(radius=max(1.2, width * 0.0025)))
    water_weight = np.asarray(mask, dtype=np.float32) / 255.0

    water = 12.0 + 9.0 * _smooth_noise(width, height, rng, 5)
    water = water * (0.85 + 0.15 * np.asarray(mask, dtype=np.float32) / 255.0)
    composite = background * (1.0 - water_weight) + water * water_weight

    rgba = np.dstack([composite, composite, composite, np.full_like(composite, 255.0)])
    image = Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), mode="RGBA")

    draw = ImageDraw.Draw(image)
    dam_center = _lonlat_to_pixel(CENTER_LON, CENTER_LAT, width, height)
    dam_length = width * 0.055 + width * 0.01 * fill
    dam = [
        (dam_center[0] - dam_length * 0.5, dam_center[1] - dam_length * 0.22),
        (dam_center[0], dam_center[1]),
        (dam_center[0] + dam_length * 0.5, dam_center[1] + dam_length * 0.22),
    ]
    draw.line(dam, fill=(245, 245, 245, 255), width=dam_width, joint="curve")

    if fill > 0.5:
        for _ in range(70):
            px = int(rng.uniform(0, width))
            py = int(rng.uniform(0, height))
            if water_weight[py, px] < 0.15:
                radius = int(rng.integers(1, max(2, width // 220)))
                shade = int(rng.uniform(190, 255))
                draw.ellipse(
                    (px - radius, py - radius, px + radius, py + radius),
                    fill=(shade, shade, shade, 255),
                )

    return image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing overlay PNGs"
    )
    parser.add_argument(
        "--size", type=int, default=1200, help="Output width/height in pixels"
    )
    args = parser.parse_args()

    width = max(400, min(4096, args.size))
    height = width
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for scene in SCENES:
        target = OUTPUT_DIR / scene["filename"]
        if target.exists() and not args.force:
            print(f"Skipping existing {target.name} (use --force to overwrite)")
            continue
        image = _build_overlay(
            width, height, scene["year"], scene["fill"], scene["dam_width"]
        )
        image.save(target, format="PNG", optimize=True)
        print(f"Wrote {target} ({image.width}x{image.height})")


if __name__ == "__main__":
    main()
