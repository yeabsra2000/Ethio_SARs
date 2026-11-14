import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.windows import from_bounds
from PIL import Image
from pathlib import Path

WEST, SOUTH, EAST, NORTH = 34.8500, 10.8500, 35.4500, 11.4500
DST_CRS = "EPSG:4326"

FILES = {
    "raw_tiffs/gerd_2019_vv.tiff": "data/overlays/gerd_2019_pre.png",
    "raw_tiffs/gerd_2021_vv.tiff": "data/overlays/gerd_2021_fill2.png",
    "raw_tiffs/gerd_2023_vv.tiff": "data/overlays/gerd_2023_fill4.png",
    "raw_tiffs/gerd_2025_vv.tiff": "data/overlays/gerd_2025_full.png",
}

Path("data/overlays").mkdir(parents=True, exist_ok=True)

for src_path, dst_path in FILES.items():
    if not Path(src_path).exists():
        continue

    with rasterio.open(src_path) as src:
        gcps, gcp_crs = src.gcps

        if src.crs is not None:
            transform, width, height = calculate_default_transform(
                src.crs, DST_CRS, src.width, src.height, *src.bounds
            )
            src_kwargs = {"src_transform": src.transform, "src_crs": src.crs}
        elif gcps:
            transform, width, height = calculate_default_transform(
                gcp_crs, DST_CRS, src.width, src.height, gcps=gcps
            )
            src_kwargs = {"gcps": gcps, "src_crs": gcp_crs}
        else:
            raise ValueError(f"No CRS or GCPs found in {src_path}")

        reprojected = np.zeros((height, width), dtype=np.float32)
        reproject(
            source=rasterio.band(src, 1),
            destination=reprojected,
            dst_transform=transform,
            dst_crs=DST_CRS,
            resampling=Resampling.bilinear,
            **src_kwargs,
        )

        # Crop to exact GERD bounding box
        win = from_bounds(WEST, SOUTH, EAST, NORTH, transform=transform).round_offsets().round_lengths()
        r0, r1 = max(0, win.row_off), min(height, win.row_off + win.height)
        c0, c1 = max(0, win.col_off), min(width, win.col_off + win.width)
        cropped = reprojected[r0:r1, c0:c1]

        valid = cropped[cropped > 0]
        if valid.size == 0:
            print(f"WARNING: {src_path} does not overlap the GERD bounding box! Pick a different scene.")
            continue

        # Convert valid radar backscatter to dB and stretch contrast
        db = 10.0 * np.log10(np.clip(cropped, 1e-6, None))
        valid_db = 10.0 * np.log10(valid)
        p2, p98 = np.percentile(valid_db, (2, 98))
        norm = np.clip((db - p2) / max(p98 - p2, 1e-6) * 255.0, 0, 255).astype(np.uint8)
        norm[cropped <= 0] = 0  # Keep out-of-swath border black

        alpha = np.where(norm > 0, 255, 0).astype(np.uint8)
        rgba = np.dstack([norm, norm, norm, alpha])
        img = Image.fromarray(rgba, mode="RGBA")
        img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
        img.save(dst_path, optimize=True)
        print(f"Saved {dst_path} -> {img.size}, {Path(dst_path).stat().st_size / 1024:.1f} KB")