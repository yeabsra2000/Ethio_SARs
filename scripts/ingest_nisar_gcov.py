"""Download, inspect, and process NISAR L-band GCOV products for GERD.

Full GCOV HDF5 products require a NASA Earthdata Login. Set
``EARTHDATA_TOKEN`` in ``.env`` before downloading. Raw files are cached under
``raw_tiffs/nisar_gcov/`` and are intentionally excluded from Git.

The processing step uses the frequency-A HH covariance term (``HHHH``), which is
RTC-calibrated gamma0 linear power on a 20 m UTM grid. It converts to dB,
computes a common Otsu threshold over both GERD crops, builds water masks, and
writes calibrated overlays plus a provenance manifest.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402

GCOV_DIR = ROOT / "raw_tiffs" / "nisar_gcov"
OVERLAY_DIR = ROOT / "data" / "overlays"
MANIFEST_PATH = ROOT / "data" / "nisar_gcov_manifest.json"

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
PRODUCT_URL = (
    "https://nisar.asf.earthdatacloud.nasa.gov/NISAR/"
    "NISAR_L2_GCOV_V1/{product}/{product}.h5"
)
CHUNK_SIZE = 8 * 1024 * 1024

WEST, SOUTH, EAST, NORTH = 34.8500, 10.8500, 35.4500, 11.4500
PIXEL_SIZE_M = 20.0
PIXEL_AREA_M2 = PIXEL_SIZE_M * PIXEL_SIZE_M
OVERLAY_SIZE = 1024
DB_VMIN, DB_VMAX = -25.0, -5.0
GCOV_GRID = "science/LSAR/GCOV/grids/frequencyA"


def product_path(product: str) -> Path:
    return GCOV_DIR / f"{product}.h5"


def _token() -> str:
    token = get_settings().earthdata_token or ""
    if not token:
        raise RuntimeError(
            "EARTHDATA_TOKEN is empty. Add a NASA Earthdata Login token to .env."
        )
    return token


def _format_bytes(value: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def download_product(product: str, force: bool = False) -> Path:
    """Download one GCOV product with HTTP range resume support."""

    GCOV_DIR.mkdir(parents=True, exist_ok=True)
    destination = product_path(product)
    partial = destination.with_suffix(".h5.part")

    if destination.exists() and destination.stat().st_size > 0 and not force:
        print(f"[skip] {destination.name} already exists")
        return destination

    if force:
        partial.unlink(missing_ok=True)

    url = PRODUCT_URL.format(product=product)
    existing = partial.stat().st_size if partial.exists() else 0
    headers = {
        "Authorization": f"Bearer {_token()}",
        "User-Agent": "Ethio-SARs/1.0 (NASA Space Apps demo)",
    }
    if existing:
        headers["Range"] = f"bytes={existing}-"

    request = urllib.request.Request(url, headers=headers)
    try:
        response = urllib.request.urlopen(request, timeout=120)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Download failed for {product}: HTTP {exc.code}") from exc

    with response:
        append = existing > 0 and response.status == 206
        if existing and not append:
            print("[restart] server ignored the range request; restarting download")
            existing = 0
        mode = "ab" if append else "wb"
        content_length = int(response.headers.get("Content-Length") or 0)
        total = existing + content_length if append else content_length
        downloaded = existing
        started = time.monotonic()
        last_report = 0.0
        print(
            f"[download] {product}\n"
            f"           {_format_bytes(total)} total, resuming at "
            f"{_format_bytes(existing)}"
        )
        with partial.open(mode) as handle:
            while True:
                chunk = response.read(CHUNK_SIZE)
                if not chunk:
                    break
                handle.write(chunk)
                downloaded += len(chunk)
                elapsed = time.monotonic() - started
                if elapsed - last_report >= 10 or downloaded == total:
                    rate = downloaded / elapsed if elapsed else 0
                    percent = (downloaded / total * 100) if total else 0
                    print(
                        f"           {percent:5.1f}%  "
                        f"{_format_bytes(downloaded)} / {_format_bytes(total)}  "
                        f"{_format_bytes(rate)}/s"
                    )
                    last_report = elapsed

    if total and partial.stat().st_size != total:
        raise RuntimeError(
            f"Incomplete download for {product}: "
            f"{partial.stat().st_size} of {total} bytes"
        )
    partial.replace(destination)
    print(f"[done] {destination} ({_format_bytes(destination.stat().st_size)})")
    return destination


def inspect_product(path: Path) -> None:
    """Print the HDF5 group/dataset tree and compact dataset metadata."""

    import h5py

    print(f"\n[inspect] {path.name}")
    with h5py.File(path, "r") as handle:
        def visitor(name: str, obj: object) -> None:
            if isinstance(obj, h5py.Dataset):
                attrs = {
                    key: value
                    for key, value in obj.attrs.items()
                    if isinstance(value, (str, int, float, bool, bytes))
                }
                print(
                    f"D {name} | shape={obj.shape} dtype={obj.dtype} "
                    f"chunks={obj.chunks} compression={obj.compression} "
                    f"attrs={attrs}"
                )
            else:
                print(f"G {name}")

        handle.visititems(visitor)
        print("[root attrs]")
        for key, value in handle.attrs.items():
            if isinstance(value, (str, int, float, bool, bytes)):
                print(f"  {key}: {value}")


def _coordinate_slice(
    coordinates: "object", low: float, high: float
) -> tuple[int, int]:
    """Return a half-open index slice covering [low, high] in a coordinate axis."""

    import numpy as np

    values = np.asarray(coordinates, dtype=float)
    if values.size < 2:
        raise ValueError("Coordinate axis is too short")
    if values[0] <= values[-1]:
        start = int(np.searchsorted(values, low, side="left"))
        stop = int(np.searchsorted(values, high, side="right"))
    else:
        start = int(np.searchsorted(-values, -high, side="left"))
        stop = int(np.searchsorted(-values, -low, side="right"))
    if stop <= start:
        raise ValueError("GERD window does not overlap the NISAR grid")
    return start, stop


def _gerd_utm_bounds() -> tuple[float, float, float, float]:
    from rasterio.warp import transform_bounds

    return transform_bounds(
        "EPSG:4326", "EPSG:32636", WEST, SOUTH, EAST, NORTH, densify_pts=21
    )


def read_gerd_crop(path: Path) -> dict:
    """Read the frequency-A HH gamma0 crop over GERD and convert it to dB."""

    import h5py
    import numpy as np

    xmin, ymin, xmax, ymax = _gerd_utm_bounds()
    with h5py.File(path, "r") as handle:
        base = GCOV_GRID
        x = handle[f"{base}/xCoordinates"][()]
        y = handle[f"{base}/yCoordinates"][()]
        x0, x1 = _coordinate_slice(x, xmin, xmax)
        y0, y1 = _coordinate_slice(y, ymin, ymax)
        hh = handle[f"{base}/HHHH"][y0:y1, x0:x1]
        mask = handle[f"{base}/mask"][y0:y1, x0:x1]
        available_pols = [
            value.decode("utf-8", "replace")
            for value in handle[f"{base}/listOfPolarizations"][()]
        ]
        center_frequency = float(
            handle[
                "science/LSAR/GCOV/metadata/sourceData/swaths/"
                "frequencyA/centerFrequency"
            ][()]
        )

    valid = (
        (mask > 0)
        & (mask < 255)
        & np.isfinite(hh)
        & (hh > 0)
    )
    db = np.full(hh.shape, np.nan, dtype=np.float32)
    db[valid] = 10.0 * np.log10(hh[valid].astype(np.float64))
    return {
        "db": db,
        "valid": valid,
        "available_polarizations": available_pols,
        "center_frequency_hz": center_frequency,
        "window": {
            "x0": x0,
            "x1": x1,
            "y0": y0,
            "y1": y1,
            "shape": [int(y1 - y0), int(x1 - x0)],
        },
        "utm_bounds": {
            "west": float(xmin),
            "south": float(ymin),
            "east": float(xmax),
            "north": float(ymax),
        },
    }


def otsu_threshold(values: "object", bins: int = 512) -> float:
    """Return an Otsu threshold in dB for a one-dimensional sample."""

    import numpy as np

    sample = np.asarray(values, dtype=np.float64)
    sample = sample[np.isfinite(sample)]
    if sample.size == 0:
        raise ValueError("No valid samples for Otsu threshold")
    histogram, edges = np.histogram(sample, bins=bins)
    histogram = histogram.astype(np.float64)
    centers = (edges[:-1] + edges[1:]) / 2.0
    weight_background = np.cumsum(histogram)
    weight_foreground = histogram.sum() - weight_background
    mean_background = (
        np.cumsum(histogram * centers) / np.maximum(weight_background, 1.0)
    )
    mean_foreground = (
        np.cumsum((histogram * centers)[::-1])[::-1] - histogram * centers
    ) / np.maximum(weight_foreground, 1.0)
    between_class_variance = (
        weight_background
        * weight_foreground
        * (mean_background - mean_foreground) ** 2
    )
    index = int(np.nanargmax(between_class_variance))
    return float(centers[index])


def _save_db_overlay(db: "object", valid: "object", path: Path) -> None:
    """Save a calibrated dB grayscale RGBA overlay with transparent no-data."""

    import numpy as np
    from PIL import Image

    clipped = np.clip(db, DB_VMIN, DB_VMAX)
    scaled = np.zeros(db.shape, dtype=np.uint8)
    scaled[valid] = (
        (clipped[valid] - DB_VMIN) / (DB_VMAX - DB_VMIN) * 255.0
    ).astype(np.uint8)
    alpha = np.where(valid, 255, 0).astype(np.uint8)
    rgba = np.dstack([scaled, scaled, scaled, alpha])
    image = Image.fromarray(rgba, mode="RGBA").resize(
        (OVERLAY_SIZE, OVERLAY_SIZE), Image.Resampling.LANCZOS
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)


def _save_water_overlay(water: "object", path: Path) -> None:
    """Save a transparent blue water-mask overlay."""

    import numpy as np
    from PIL import Image

    mask = (water.astype(np.uint8) * 255)
    image = Image.fromarray(mask, mode="L").resize(
        (OVERLAY_SIZE, OVERLAY_SIZE), Image.Resampling.NEAREST
    )
    alpha = np.asarray(image, dtype=np.uint8)
    rgba = np.zeros((OVERLAY_SIZE, OVERLAY_SIZE, 4), dtype=np.uint8)
    rgba[..., 0] = 12
    rgba[..., 1] = 126
    rgba[..., 2] = 255
    rgba[..., 3] = (alpha > 0).astype(np.uint8) * 190
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, mode="RGBA").save(path, optimize=True)


def process_products() -> dict:
    """Build calibrated masks, overlays, and change statistics for both dates."""

    import numpy as np

    crops: dict[str, dict] = {}
    for date_label, product in PRODUCTS.items():
        path = product_path(product)
        if not path.exists():
            raise FileNotFoundError(
                f"Missing {path}. Run --download first."
            )
        crops[date_label] = read_gerd_crop(path)
        print(
            f"[read] {date_label} {product} | "
            f"window={crops[date_label]['window']['shape']} | "
            f"valid={int(crops[date_label]['valid'].sum()):,}"
        )

    combined = np.concatenate(
        [
            crop["db"][crop["valid"]]
            for crop in crops.values()
        ]
    )
    threshold = otsu_threshold(combined)
    print(f"[threshold] common Otsu over both GERD crops: {threshold:.3f} dB")

    scenes: list[dict] = []
    water_masks: dict[str, object] = {}
    for date_label, product in PRODUCTS.items():
        crop = crops[date_label]
        valid = crop["valid"]
        water = valid & (crop["db"] <= threshold)
        water_masks[date_label] = water
        water_area = float(water.sum()) * PIXEL_AREA_M2 / 1e6
        valid_area = float(valid.sum()) * PIXEL_AREA_M2 / 1e6
        date_slug = date_label.replace("-", "_")
        overlay_path = OVERLAY_DIR / f"nisar_{date_slug}_gcov.png"
        water_path = OVERLAY_DIR / f"nisar_{date_slug}_water.png"
        _save_db_overlay(crop["db"], valid, overlay_path)
        _save_water_overlay(water, water_path)

        scenes.append(
            {
                "date": date_label,
                "product_id": product,
                "platform": "NISAR",
                "instrument": "NISAR L-band SAR",
                "frequency_band": "L-band",
                "center_frequency_hz": crop["center_frequency_hz"],
                "polarization": "HH",
                "available_polarizations": crop["available_polarizations"],
                "product_type": "GCOV",
                "processing_level": "L2",
                "grid": GCOV_GRID,
                "resolution_m": PIXEL_SIZE_M,
                "data_source": "NISAR L2 GCOV HDF5 frequency-A HHHH gamma0",
                "calibration": (
                    "RTC-calibrated gamma0 linear power; dB = 10*log10(HHHH)"
                ),
                "water_area_sq_km": round(water_area, 2),
                "valid_area_sq_km": round(valid_area, 2),
                "water_fraction": round(water_area / valid_area, 6),
                "water_pixels": int(water.sum()),
                "valid_pixels": int(valid.sum()),
                "threshold_db": round(threshold, 3),
                "overlay_url": f"/static/overlays/{overlay_path.name}",
                "water_mask_url": f"/static/overlays/{water_path.name}",
                "hdf5_file": product_path(product).name,
                "hdf5_bytes": int(product_path(product).stat().st_size),
                "window": crop["window"],
                "utm_bounds": crop["utm_bounds"],
            }
        )

    dates = sorted(water_masks)
    before_date, after_date = dates[0], dates[1]
    before = water_masks[before_date]
    after = water_masks[after_date]
    persistent = int((before & after).sum())
    lost = int((before & ~after).sum())
    new = int((after & ~before).sum())
    union = int((before | after).sum())

    change = {
        "before": before_date,
        "after": after_date,
        "threshold_db": round(threshold, 3),
        "pixel_area_m2": PIXEL_AREA_M2,
        "persistent_sq_km": round(persistent * PIXEL_AREA_M2 / 1e6, 2),
        "lost_sq_km": round(lost * PIXEL_AREA_M2 / 1e6, 2),
        "new_sq_km": round(new * PIXEL_AREA_M2 / 1e6, 2),
        "net_change_sq_km": round((new - lost) * PIXEL_AREA_M2 / 1e6, 2),
        "union_sq_km": round(union * PIXEL_AREA_M2 / 1e6, 2),
        "jaccard": round(persistent / union, 6) if union else None,
    }

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mission": "NISAR",
        "method": (
            "Frequency-A HHHH gamma0 linear power converted to dB, cropped to "
            "the GERD window in EPSG:32636, common Otsu threshold across both "
            "dates, valid GCOV mask (0 < mask < 255), 20 m pixel area."
        ),
        "bounds_wgs84": {
            "west": WEST,
            "south": SOUTH,
            "east": EAST,
            "north": NORTH,
        },
        "threshold_db": round(threshold, 3),
        "pixel_size_m": PIXEL_SIZE_M,
        "pixel_area_m2": PIXEL_AREA_M2,
        "scenes": scenes,
        "change": change,
        "caveats": [
            "Threshold-based HH water mask, not an independently validated product.",
            "L-band HH is not directly comparable to Sentinel-1 C-band VV.",
            "The two NISAR dates are 12 days apart; small changes may be noise.",
            "Noise correction was not applied by the NISAR processor.",
        ],
    }

    OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[manifest] {MANIFEST_PATH}")
    for scene in scenes:
        print(
            f"{scene['date']} | {scene['product_id']} | "
            f"HH | {scene['water_area_sq_km']:,.1f} km2 "
            f"({scene['water_fraction'] * 100:.1f}%) | "
            f"{scene['overlay_url']}"
        )
    print(
        f"change {change['before']} -> {change['after']} | "
        f"net {change['net_change_sq_km']:+.1f} km2 | "
        f"persistent {change['persistent_sq_km']:.1f} | "
        f"lost {change['lost_sq_km']:.1f} | new {change['new_sq_km']:.1f} | "
        f"Jaccard {change['jaccard']:.4f}"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download missing GCOV products.",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Print HDF5 structure for downloaded products.",
    )
    parser.add_argument(
        "--process",
        action="store_true",
        help="Build calibrated GERD masks, overlays, and change statistics.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Restart downloads even when complete files exist.",
    )
    args = parser.parse_args()

    if not args.download and not args.inspect and not args.process:
        parser.print_help()
        return

    for date_label, product in PRODUCTS.items():
        print(f"\n=== {date_label} ===")
        path = product_path(product)
        if args.download:
            path = download_product(product, force=args.force)
        if args.inspect:
            if not path.exists():
                print(f"[missing] {path}")
                continue
            inspect_product(path)
        if args.process and not path.exists():
            raise FileNotFoundError(
                f"Missing {path}. Run --download before --process."
            )

    if args.process:
        process_products()


if __name__ == "__main__":
    main()
