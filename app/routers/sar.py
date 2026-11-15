"""SAR catalog and live NASA ASF search endpoints."""

from fastapi import APIRouter, HTTPException

from app.schemas import (
    GerdScene,
    GerdTimelineResponse,
    LiveSarSearchRequest,
    LiveSarSearchResponse,
    NisarChangeResponse,
)
from app.services.asf_client import search_live
from app.services.gerd_data import get_nisar_change, get_scene, get_timeline

router = APIRouter(prefix="/api/sar", tags=["SAR"])


@router.get(
    "/gerd/timeline",
    response_model=GerdTimelineResponse,
    summary="Curated multi-year GERD SAR timeline",
)
def gerd_timeline() -> GerdTimelineResponse:
    """Return pre-rendered GERD overlays ready for 3D terrain draping."""

    return get_timeline()


@router.get(
    "/gerd/scenes/{scene_id}",
    response_model=GerdScene,
    summary="Single curated GERD scene",
)
def gerd_scene(scene_id: str) -> GerdScene:
    """Return a single curated scene by identifier."""

    scene = get_scene(scene_id)
    if scene is None:
        raise HTTPException(status_code=404, detail=f"Unknown scene id: {scene_id}")
    return scene


@router.get(
    "/nisar/change",
    response_model=NisarChangeResponse,
    summary="Calibrated NISAR GCOV water-extent change",
)
def nisar_change() -> NisarChangeResponse:
    """Return the calibrated 12-day NISAR water-mask change over GERD."""

    change = get_nisar_change()
    if change is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Calibrated NISAR GCOV outputs are not available. Run "
                "scripts/ingest_nisar_gcov.py --process."
            ),
        )
    return change


@router.post(
    "/search-live",
    response_model=LiveSarSearchResponse,
    summary="Live NASA ASF search for custom coordinates",
)
def search_live_endpoint(request: LiveSarSearchRequest) -> LiveSarSearchResponse:
    """Query NASA's Alaska Satellite Facility for Sentinel-1 / NISAR scenes."""

    return search_live(request)
