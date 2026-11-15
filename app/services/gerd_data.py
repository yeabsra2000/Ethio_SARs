"""Curated GERD / Lake Nigat multi-year SAR catalog."""

import json

from app.config import DATA_DIR
from app.schemas import (
    Bounds,
    Center,
    GerdScene,
    GerdTimelineResponse,
    NisarChangeResponse,
)

GERD_CENTER = Center(lat=11.215, lon=35.093)
GERD_BOUNDS = Bounds(west=34.8500, south=10.8500, east=35.4500, north=11.4500)

LOCATION_NAME = "Grand Ethiopian Renaissance Dam (Lake Nigat)"

SENTINEL_AREA_NOTE = (
    "Curated narrative estimate for the demo, not a live measurement from the "
    "raster."
)
NISAR_AREA_NOTE = (
    "Calibrated NISAR L2 GCOV frequency-A HH water mask using a common Otsu "
    "threshold across both dates; threshold-based and not independently "
    "validated. L-band HH is not directly comparable to Sentinel-1 C-band VV."
)
NISAR_CHANGE_METHOD = (
    "Frequency-A HHHH gamma0 linear power converted to dB, cropped to the GERD "
    "window in EPSG:32636, common Otsu threshold across both dates, valid GCOV "
    "mask (0 < mask < 255), 20 m pixel area."
)

SCENES: list[GerdScene] = [
    GerdScene(
        id="gerd_2019",
        year=2019,
        date="2019-11-15",
        label="Pre-Filling Baseline",
        sensor="Sentinel-1 C-Band SAR (VV Polarization)",
        platform="Sentinel-1",
        frequency_band="C-band",
        polarization="VV",
        product_type="GRD_HD",
        overlay_url="/static/overlays/gerd_2019_pre.png",
        water_area_sq_km=48.2,
        area_note=SENTINEL_AREA_NOTE,
        backscatter_summary=(
            "High radar backscatter across the river gorge; only the narrow "
            "natural Blue Nile channel is visible before impoundment."
        ),
        bounds=GERD_BOUNDS,
    ),
    GerdScene(
        id="gerd_2021",
        year=2021,
        date="2021-11-08",
        label="First Filling Phase",
        sensor="Sentinel-1 C-Band SAR (VV Polarization)",
        platform="Sentinel-1",
        frequency_band="C-band",
        polarization="VV",
        product_type="GRD_HD",
        overlay_url="/static/overlays/gerd_2021_fill2.png",
        water_area_sq_km=363.0,
        area_note=SENTINEL_AREA_NOTE,
        backscatter_summary=(
            "Early reservoir pool appears as smooth dark patches near the dam "
            "as the first impoundment spreads upstream."
        ),
        bounds=GERD_BOUNDS,
    ),
    GerdScene(
        id="gerd_2023",
        year=2023,
        date="2023-11-02",
        label="Fourth Filling Phase",
        sensor="Sentinel-1 C-Band SAR (VV Polarization)",
        platform="Sentinel-1",
        frequency_band="C-band",
        polarization="VV",
        product_type="GRD_HD",
        overlay_url="/static/overlays/gerd_2023_fill4.png",
        water_area_sq_km=1100.0,
        area_note=SENTINEL_AREA_NOTE,
        backscatter_summary=(
            "A large contiguous specular water body now dominates the valley "
            "floor, bounded by bright double-bounce returns from steep banks."
        ),
        bounds=GERD_BOUNDS,
    ),
    GerdScene(
        id="gerd_2025",
        year=2025,
        date="2025-11-10",
        label="Full Reservoir Capacity",
        sensor="Sentinel-1A C-Band SAR (VV Polarization)",
        platform="Sentinel-1",
        frequency_band="C-band",
        polarization="VV",
        product_type="GRD_HD",
        overlay_url="/static/overlays/gerd_2025_full.png",
        water_area_sq_km=1874.0,
        area_note=SENTINEL_AREA_NOTE,
        backscatter_summary=(
            "Extensive specular reflection (pitch-black SAR signature) indicates "
            "deep standing water across roughly 1,874 sq km at full supply level."
        ),
        bounds=GERD_BOUNDS,
    ),
    GerdScene(
        id="gerd_2026_10_25",
        year=2026,
        date="2026-10-25",
        label="NISAR L-Band Baseline",
        sensor="NISAR L-Band SAR (HH GCOV)",
        platform="NISAR",
        frequency_band="L-band",
        polarization="HH",
        product_type="GCOV",
        data_source="NISAR L2 GCOV HDF5 frequency-A HHHH gamma0",
        overlay_url="/static/overlays/nisar_2026_10_25_gcov.png",
        water_mask_url="/static/overlays/nisar_2026_10_25_water.png",
        water_area_sq_km=936.6,
        threshold_db=-14.053,
        area_note=NISAR_AREA_NOTE,
        backscatter_summary=(
            "Calibrated NISAR L-band HH gamma0 shows the reservoir as a "
            "low-backscatter area, with brighter returns from surrounding "
            "terrain and the dam infrastructure."
        ),
        bounds=GERD_BOUNDS,
    ),
    GerdScene(
        id="gerd_2026_11_06",
        year=2026,
        date="2026-11-06",
        label="NISAR 12-Day Repeat",
        sensor="NISAR L-Band SAR (HH GCOV)",
        platform="NISAR",
        frequency_band="L-band",
        polarization="HH",
        product_type="GCOV",
        data_source="NISAR L2 GCOV HDF5 frequency-A HHHH gamma0",
        overlay_url="/static/overlays/nisar_2026_11_06_gcov.png",
        water_mask_url="/static/overlays/nisar_2026_11_06_water.png",
        water_area_sq_km=958.6,
        threshold_db=-14.053,
        area_note=NISAR_AREA_NOTE,
        backscatter_summary=(
            "The calibrated 12-day repeat HH GCOV keeps the same "
            "low-backscatter reservoir signature, while L-band sensitivity "
            "highlights vegetation and soil-moisture variation around the "
            "shoreline."
        ),
        bounds=GERD_BOUNDS,
    ),
]

def _load_nisar_manifest() -> dict | None:
    """Read the calibrated GCOV manifest generated by the ingest script."""

    path = DATA_DIR / "nisar_gcov_manifest.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _apply_nisar_manifest(manifest: dict | None) -> None:
    """Overlay calibrated areas and overlay URLs onto the curated NISAR scenes."""

    if not manifest:
        return
    by_date = {
        item.get("date"): item
        for item in manifest.get("scenes", [])
        if item.get("date")
    }
    for scene in SCENES:
        if scene.platform != "NISAR":
            continue
        item = by_date.get(scene.date.isoformat())
        if not item:
            continue
        scene.water_area_sq_km = float(item["water_area_sq_km"])
        scene.overlay_url = item["overlay_url"]
        scene.water_mask_url = item.get("water_mask_url")
        scene.data_source = item.get("data_source")
        scene.threshold_db = item.get("threshold_db")
        scene.area_note = NISAR_AREA_NOTE


_NISAR_MANIFEST = _load_nisar_manifest()
_apply_nisar_manifest(_NISAR_MANIFEST)

_SCENES_BY_ID = {scene.id: scene for scene in SCENES}


def get_timeline() -> GerdTimelineResponse:
    """Return the curated GERD timeline payload."""

    return GerdTimelineResponse(
        location_name=LOCATION_NAME,
        center=GERD_CENTER,
        bounds=GERD_BOUNDS,
        scenes=SCENES,
    )


def get_scene(scene_id: str) -> GerdScene | None:
    """Look up a curated scene by its identifier."""

    return _SCENES_BY_ID.get(scene_id)


def get_nisar_change() -> NisarChangeResponse | None:
    """Return calibrated NISAR water-extent change statistics, if processed."""

    if not _NISAR_MANIFEST:
        return None
    change = _NISAR_MANIFEST.get("change") or {}
    before_date = change.get("before")
    after_date = change.get("after")
    if not before_date or not after_date:
        return None
    before = get_scene(f"gerd_{before_date.replace('-', '_')}")
    after = get_scene(f"gerd_{after_date.replace('-', '_')}")
    if before is None or after is None:
        return None
    return NisarChangeResponse(
        before=before,
        after=after,
        threshold_db=float(change["threshold_db"]),
        persistent_sq_km=float(change["persistent_sq_km"]),
        lost_sq_km=float(change["lost_sq_km"]),
        new_sq_km=float(change["new_sq_km"]),
        net_change_sq_km=float(change["net_change_sq_km"]),
        union_sq_km=float(change["union_sq_km"]),
        jaccard=(
            float(change["jaccard"])
            if change.get("jaccard") is not None
            else None
        ),
        method=str(_NISAR_MANIFEST.get("method") or NISAR_CHANGE_METHOD),
        generated_at=_NISAR_MANIFEST.get("generated_at"),
        caveats=list(_NISAR_MANIFEST.get("caveats") or []),
    )
