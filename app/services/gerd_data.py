"""Curated GERD / Lake Nigat multi-year SAR catalog."""

from app.schemas import Bounds, Center, GerdScene, GerdTimelineResponse

GERD_CENTER = Center(lat=11.215, lon=35.093)
GERD_BOUNDS = Bounds(west=34.8500, south=10.8500, east=35.4500, north=11.4500)

LOCATION_NAME = "Grand Ethiopian Renaissance Dam (Lake Nigat)"

SENTINEL_AREA_NOTE = (
    "Curated narrative estimate for the demo, not a live measurement from the "
    "raster."
)
NISAR_AREA_NOTE = (
    "Approximate low-backscatter area from the public NISAR browse image using "
    "an Otsu threshold; not a calibrated water mask and not directly comparable "
    "to the Sentinel-1 estimates."
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
        sensor="NISAR L-Band SAR (HH/HV Polarization)",
        platform="NISAR",
        frequency_band="L-band",
        polarization="HH/HV",
        product_type="GCOV",
        overlay_url="/static/overlays/nisar_2026_10_25.png",
        water_area_sq_km=1110.2,
        area_note=NISAR_AREA_NOTE,
        backscatter_summary=(
            "NISAR L-band HH browse image shows the reservoir as a broad "
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
        sensor="NISAR L-Band SAR (HH Polarization)",
        platform="NISAR",
        frequency_band="L-band",
        polarization="HH",
        product_type="GCOV",
        overlay_url="/static/overlays/nisar_2026_11_06.png",
        water_area_sq_km=1043.2,
        area_note=NISAR_AREA_NOTE,
        backscatter_summary=(
            "The 12-day repeat NISAR browse image keeps the same low-backscatter "
            "reservoir signature, while L-band sensitivity highlights vegetation "
            "and soil-moisture variation around the shoreline."
        ),
        bounds=GERD_BOUNDS,
    ),
]

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
