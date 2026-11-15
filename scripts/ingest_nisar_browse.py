"""Build GERD map overlays from public NISAR L-band GCOV browse images.

The full NISAR GCOV HDF5 products require a NASA Earthdata Login. The ASF
``LATLON`` browse PNGs are public, already geocoded to EPSG:4326, and include a
KML file with the exact LatLonQuad. This script downloads those small browse
assets, crops them to the GERD analysis window, and writes RGBA PNGs for the
map. It also reports a browse-derived low-backscatter area estimate; that value
is not a calibrated water mask.
"""

from __future__ import annotations

import argparse
import math
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BROWSE_DIR = ROOT / "raw_tiffs" / "nisar_browse"
OVERLAY_DIR = ROOT / "data" / "overlays"

WEST, SOUTH, EAST, NORTH = 34.8500, 10.8500, 35.4500, 11.4500
OVERLAY_SIZE = 1024
ASF_BROWSE = (
    "https://nisar.asf.earthdatacloud.nasa.gov/BROWSE/"
    "NISAR_L2_GCOV_V1/{product}/{product}_{suffix}"
)

PRODUCTS = {
    "2026-10-25": (
        "NISAR_L2_PR_GCOV_034_021_D_083_2005_DHDH_A_"
        "20261025T160621_20261025T160656_P05036_N_F_J_001"
    ),
    "2026-11-06": (
        "NISAR_L2_PR_GCOV_035_021_D_083_2005_SHSH_A_"
        "20261106T160622_20261106T160656_P05036_N_F_J_001"
    ),
}


def download(url: str, destination: Path) -> None:
    """Download a public browse asset unless it already exists."""

    if destination.exists() and destination.stat().st_size > 0:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Ethio-SARs/1.0 (NASA Space Apps demo)"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        destination.write_bytes(response.read())


def parse_kml_bounds(kml_path: Path) -> tuple[float, float, float, float]:
    """Return west, south, east, north from a NISAR LatLonQuad KML."""

    tree = ET.parse(kml_path)
    coordinates = tree.findtext(".//coordinates")
    if not coordinates:
        raise ValueError(f"No coordinates found in {kml_path}")
    pairs = [
        (float(lon), float(lat))
        for lon, lat in re.findall(
            r"(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)", coordinates
        )
    ]
    if not pairs:
        raise ValueError(f"Could not parse coordinates in {kml_path}")
    lons = [point[0] for point in pairs]
    lats = [point[1] for point in pairs]
    return min(lons), min(lats), max(lons), max(lats)


def otsu_threshold(image: np.ndarray) -> int:
    """Compute an Otsu threshold for an 8-bit grayscale image."""

    histogram = np.bincount(image.ravel(), minlength=256).astype(float)
    total = image.size
    sum_total = np.dot(np.arange(256), histogram)
    weight_background = 0.0
    sum_background = 0.0
    best_threshold = 0
    best_variance = -1.0
    for threshold in range(256):
        weight_background += histogram[threshold]
        if weight_background == 0:
            continue
        weight_foreground = total - weight_background
        if weight_foreground == 0:
            break
        sum_background += threshold * histogram[threshold]
        mean_background = sum_background / weight_background
        mean_foreground = (sum_total - sum_background) / weight_foreground
        variance = (
            weight_background
            * weight_foreground
            * (mean_background - mean_foreground) ** 2
        )
        if variance > best_variance:
            best_variance = variance
            best_threshold = threshold
    return best_threshold


def crop_to_gerd(image: np.ndarray, bounds: tuple[float, float, float, float]) -> np.ndarray:
    """Crop a north-up EPSG:4326 browse image to the GERD window."""

    west, south, east, north = bounds
    height, width = image.shape
    x0 = int(round((WEST - west) / (east - west) * width))
    x1 = int(round((EAST - west) / (east - west) * width))
    y0 = int(round((north - NORTH) / (north - south) * height))
    y1 = int(round((north - SOUTH) / (north - south) * height))
    x0, x1 = max(0, x0), min(width, x1)
    y0, y1 = max(0, y0), min(height, y1)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("NISAR browse image does not overlap the GERD window")
    return image[y0:y1, x0:x1]


def gerd_area_sq_km() -> float:
    """Approximate area of the GERD window in square kilometres."""

    mean_latitude = math.radians((SOUTH + NORTH) / 2.0)
    width_km = (EAST - WEST) * 111.320 * math.cos(mean_latitude)
    height_km = (NORTH - SOUTH) * 110.574
    return width_km * height_km


def build_overlay(date_label: str, product: str, force: bool = False) -> dict:
    """Download, crop, and save one NISAR browse overlay."""

    png_path = BROWSE_DIR / f"{product}_LATLON.png"
    kml_path = BROWSE_DIR / f"{product}_LATLON.kml"
    download(ASF_BROWSE.format(product=product, suffix="LATLON.png"), png_path)
    download(ASF_BROWSE.format(product=product, suffix="LATLON.kml"), kml_path)

    bounds = parse_kml_bounds(kml_path)
    source = np.array(Image.open(png_path).convert("L"))
    crop = crop_to_gerd(source, bounds)

    threshold = otsu_threshold(crop)
    low_backscatter_fraction = float((crop <= threshold).mean())
    estimated_area = low_backscatter_fraction * gerd_area_sq_km()

    overlay_path = OVERLAY_DIR / f"nisar_{date_label.replace('-', '_')}.png"
    if force or not overlay_path.exists():
        display = Image.fromarray(crop, mode="L").resize(
            (OVERLAY_SIZE, OVERLAY_SIZE), Image.Resampling.LANCZOS
        )
        rgba = np.dstack(
            [
                np.array(display),
                np.array(display),
                np.array(display),
                np.full((OVERLAY_SIZE, OVERLAY_SIZE), 255, dtype=np.uint8),
            ]
        )
        Image.fromarray(rgba, mode="RGBA").save(overlay_path, optimize=True)

    return {
        "date": date_label,
        "product": product,
        "kml_bounds": bounds,
        "crop_pixels": (int(crop.shape[1]), int(crop.shape[0])),
        "otsu_threshold": threshold,
        "low_backscatter_fraction": low_backscatter_fraction,
        "low_backscatter_area_sq_km": estimated_area,
        "overlay": str(overlay_path.relative_to(ROOT)).replace("\\", "/"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild overlays even when the PNG already exists.",
    )
    args = parser.parse_args()

    OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
    for date_label, product in PRODUCTS.items():
        result = build_overlay(date_label, product, force=args.force)
        print(
            f"{result['date']} | {result['product']} | "
            f"crop={result['crop_pixels'][0]}x{result['crop_pixels'][1]} | "
            f"Otsu={result['otsu_threshold']} | "
            f"low-backscatter={result['low_backscatter_area_sq_km']:.1f} km2 "
            f"({result['low_backscatter_fraction'] * 100:.1f}%) | "
            f"{result['overlay']}"
        )


if __name__ == "__main__":
    main()
