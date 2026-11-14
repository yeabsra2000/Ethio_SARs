"""Curated GERD / Lake Nigat multi-year SAR catalog."""

from app.schemas import Bounds, Center, GerdScene, GerdTimelineResponse

GERD_CENTER = Center(lat=11.215, lon=35.093)
GERD_BOUNDS = Bounds(west=34.8500, south=10.8500, east=35.4500, north=11.4500)

LOCATION_NAME = "Grand Ethiopian Renaissance Dam (Lake Nigat)"

SCENES: list[GerdScene] = [
    GerdScene(
        id="gerd_2019",
        year=2019,
        date="2019-11-15",
        label="Pre-Filling Baseline",
        sensor="Sentinel-1 C-Band SAR (VV Polarization)",
        overlay_url="/static/overlays/gerd_2019_pre.png",
        water_area_sq_km=48.2,
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
        overlay_url="/static/overlays/gerd_2021_fill2.png",
        water_area_sq_km=363.0,
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
        overlay_url="/static/overlays/gerd_2023_fill4.png",
        water_area_sq_km=1100.0,
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
        sensor="NISAR / Sentinel-1 SAR",
        overlay_url="/static/overlays/gerd_2025_full.png",
        water_area_sq_km=1874.0,
        backscatter_summary=(
            "Extensive specular reflection (pitch-black SAR signature) indicates "
            "deep standing water across roughly 1,874 sq km at full supply level."
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
