"""Live NASA Alaska Satellite Facility (ASF) search wrapper."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Iterable

from app.schemas import (
    Bounds,
    Center,
    LiveSarScene,
    LiveSarSearchRequest,
    LiveSarSearchResponse,
)

logger = logging.getLogger(__name__)

try:  # pragma: no cover - import guard keeps the API bootable without the SDK
    import asf_search
except Exception:  # noqa: BLE001 - any import failure is non-fatal at boot
    asf_search = None  # type: ignore[assignment]


def _build_wkt(lat: float, lon: float, buffer_deg: float = 0.1) -> str:
    """Build a small WKT polygon (~0.1 degree box) around a point."""

    west = max(-180.0, lon - buffer_deg)
    east = min(180.0, lon + buffer_deg)
    south = max(-90.0, lat - buffer_deg)
    north = min(90.0, lat + buffer_deg)
    return (
        f"POLYGON(({west} {south}, {east} {south}, {east} {north}, "
        f"{west} {north}, {west} {south}))"
    )


def _platforms() -> list[Any]:
    """Return the Sentinel-1 / NISAR platform selectors supported by the SDK."""

    if asf_search is None:
        return []
    platform = getattr(asf_search, "PLATFORM", None)
    if platform is None:
        return ["Sentinel-1", "NISAR"]
    selectors: list[Any] = []
    for name in ("SENTINEL1", "NISAR"):
        value = getattr(platform, name, None)
        if value is not None:
            selectors.append(value)
    return selectors or ["Sentinel-1", "NISAR"]


def _to_iso(value: date | str) -> str:
    return value.isoformat() if isinstance(value, date) else str(value)


def _flatten_coords(value: Any) -> Iterable[tuple[float, float]]:
    """Yield (lon, lat) pairs from a GeoJSON coordinate structure."""

    if isinstance(value, (list, tuple)):
        if (
            len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            yield float(value[0]), float(value[1])
        else:
            for item in value:
                yield from _flatten_coords(item)


def _extract_bounds(result: Any, properties: dict[str, Any]) -> Bounds | None:
    """Best-effort extraction of a bounding box from an ASF result."""

    raw_bbox = properties.get("bbox")
    if isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) == 4:
        try:
            west, south, east, north = (float(v) for v in raw_bbox)
            return Bounds(west=west, south=south, east=east, north=north)
        except (TypeError, ValueError):
            pass

    geometry = getattr(result, "geometry", None)
    if geometry is None:
        geometry = properties.get("geometry")

    if geometry is not None:
        bounds = getattr(geometry, "bounds", None)
        if bounds and len(bounds) == 4:
            west, south, east, north = (float(v) for v in bounds)
            return Bounds(west=west, south=south, east=east, north=north)

        coords = geometry.get("coordinates") if isinstance(geometry, dict) else None
        if coords:
            points = list(_flatten_coords(coords))
            if points:
                lons = [point[0] for point in points]
                lats = [point[1] for point in points]
                return Bounds(
                    west=min(lons),
                    south=min(lats),
                    east=max(lons),
                    north=max(lats),
                )

    return None


def _extract_center(properties: dict[str, Any], bounds: Bounds | None) -> Center | None:
    lat = properties.get("centerLat")
    lon = properties.get("centerLon")
    if lat is not None and lon is not None:
        try:
            return Center(lat=float(lat), lon=float(lon))
        except (TypeError, ValueError):
            pass
    if bounds is not None:
        return Center(
            lat=(bounds.south + bounds.north) / 2.0,
            lon=(bounds.west + bounds.east) / 2.0,
        )
    return None


def _first(value: Any) -> Any:
    """Return the first element for list-valued ASF properties."""

    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _normalize_result(result: Any) -> LiveSarScene:
    properties: dict[str, Any] = dict(getattr(result, "properties", {}) or {})
    bounds = _extract_bounds(result, properties)
    polarization = _first(
        properties.get("polarization") or properties.get("polarizations")
    )
    browse = _first(properties.get("browse") or properties.get("browse_url"))
    download = _first(properties.get("downloadUrl") or properties.get("url"))

    return LiveSarScene(
        scene_id=str(
            _first(properties.get("sceneName"))
            or _first(properties.get("fileID"))
            or _first(properties.get("sceneId"))
            or "unknown"
        ),
        acquisition_time=_first(
            properties.get("startTime") or properties.get("start_time")
        ),
        platform=_first(properties.get("platform")),
        polarization=str(polarization) if polarization is not None else None,
        browse_url=browse,
        download_url=download,
        bounds=bounds,
        center=_extract_center(properties, bounds),
    )


def search_live(request: LiveSarSearchRequest) -> LiveSarSearchResponse:
    """Search NASA ASF for recent SAR scenes over a coordinate.

    Any SDK/network failure is converted into a clean, user-facing fallback
    message so the frontend demo never hard-fails.
    """

    if asf_search is None:
        return LiveSarSearchResponse(
            count=0,
            results=[],
            message=(
                "The NASA ASF SDK (asf-search) is not available in this "
                "environment. Install it to enable live scene search."
            ),
        )

    platforms = _platforms()
    wkt = _build_wkt(request.lat, request.lon)

    try:
        search_kwargs: dict[str, Any] = {
            "intersectsWith": wkt,
            "processingLevel": "GRD_HD",
            "start": _to_iso(request.start_date),
            "end": _to_iso(request.end_date),
            "maxResults": request.max_results,
        }
        if platforms:
            search_kwargs["platform"] = platforms

        raw_results = asf_search.geo_search(**search_kwargs)
        results = [_normalize_result(item) for item in raw_results]
    except Exception as exc:  # noqa: BLE001 - external service boundary
        logger.warning("ASF geo_search failed: %s", exc)
        return LiveSarSearchResponse(
            count=0,
            results=[],
            message=(
                "Live NASA ASF search is temporarily unavailable (the service "
                "may be timing out). Please retry in a moment or use the "
                "curated GERD timeline."
            ),
        )

    if not results:
        return LiveSarSearchResponse(
            count=0,
            results=[],
            message=(
                "No Sentinel-1 or NISAR GRD scenes matched this coordinate and "
                "date window. Try widening the date range."
            ),
        )

    return LiveSarSearchResponse(count=len(results), results=results)
