"""Live NASA Alaska Satellite Facility (ASF) search wrapper."""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
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

ASF_SEARCH_URL = "https://api.daac.asf.alaska.edu/services/search/param"
ASF_QUERIES = (
    {"platform": "Sentinel-1", "processingLevel": "GRD_HD"},
    {"platform": "NISAR", "processingLevel": "GCOV"},
)


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


def _parse_wkt_bounds(value: Any) -> Bounds | None:
    """Extract a bounding box from an ASF WKT polygon string."""

    if not isinstance(value, str):
        return None
    matches = re.findall(
        r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", value
    )
    if not matches:
        return None
    lons = [float(lon) for lon, _ in matches]
    lats = [float(lat) for _, lat in matches]
    return Bounds(
        west=min(lons),
        south=min(lats),
        east=max(lons),
        north=max(lats),
    )


def _extract_bounds(result: Any, properties: dict[str, Any]) -> Bounds | None:
    """Best-effort extraction of a bounding box from an ASF result."""

    raw_bbox = properties.get("bbox")
    if isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) == 4:
        try:
            west, south, east, north = (float(v) for v in raw_bbox)
            return Bounds(west=west, south=south, east=east, north=north)
        except (TypeError, ValueError):
            pass

    wkt_bounds = _parse_wkt_bounds(
        properties.get("stringFootprint")
        or properties.get("shape")
        or (properties.get("geometry") if isinstance(properties.get("geometry"), str) else None)
    )
    if wkt_bounds is not None:
        return wkt_bounds

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


def _infer_polarization(properties: dict[str, Any], scene_id: str) -> str | None:
    polarization = _first(
        properties.get("polarization") or properties.get("polarizations")
    )
    if polarization:
        return str(polarization)
    if "_SHSH_" in scene_id:
        return "HH"
    if "_DHDH_" in scene_id:
        return "HH/HV"
    if "_SHSV_" in scene_id:
        return "HV"
    return None


def _infer_frequency_band(properties: dict[str, Any]) -> str | None:
    band = _first(properties.get("frequencyBand"))
    if band:
        return str(band)
    platform = str(properties.get("platform") or "").upper()
    sensor = str(properties.get("sensor") or "").upper()
    if "NISAR" in platform or "L-SAR" in sensor:
        return "L-band"
    if "SENTINEL-1" in platform or "C-SAR" in sensor:
        return "C-band"
    return None


def _normalize_result(result: Any) -> LiveSarScene:
    raw_properties = getattr(result, "properties", None)
    if isinstance(raw_properties, dict):
        properties: dict[str, Any] = dict(raw_properties)
    elif isinstance(result, dict):
        properties = dict(result.get("properties") or result)
    else:
        properties = {}

    bounds = _extract_bounds(result, properties)
    scene_id = str(
        _first(properties.get("sceneName"))
        or _first(properties.get("granuleName"))
        or _first(properties.get("productName"))
        or _first(properties.get("sceneId"))
        or _first(properties.get("fileName"))
        or "unknown"
    )
    browse = _first(properties.get("browse") or properties.get("browse_url"))
    download = _first(properties.get("downloadUrl") or properties.get("url"))

    return LiveSarScene(
        scene_id=scene_id,
        acquisition_time=_first(
            properties.get("startTime") or properties.get("start_time")
        ),
        platform=_first(properties.get("platform")),
        frequency_band=_infer_frequency_band(properties),
        polarization=_infer_polarization(properties, scene_id),
        processing_level=_first(properties.get("processingLevel")),
        browse_url=browse,
        download_url=download,
        bounds=bounds,
        center=_extract_center(properties, bounds),
    )


def _flatten_results(payload: Any) -> list[dict[str, Any]]:
    """ASF may return a list, a nested list, or a single result object."""

    if isinstance(payload, dict):
        scene_keys = ("sceneId", "granuleName", "productName", "fileName", "sceneName")
        return [payload] if any(key in payload for key in scene_keys) else []
    if isinstance(payload, list):
        flattened: list[dict[str, Any]] = []
        for item in payload:
            flattened.extend(_flatten_results(item))
        return flattened
    return []


def _search_query(
    request: LiveSarSearchRequest,
    wkt: str,
    platform: str,
    processing_level: str,
) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "platform": platform,
            "processingLevel": processing_level,
            "intersectsWith": wkt,
            "start": _to_iso(request.start_date),
            "end": _to_iso(request.end_date),
            "maxResults": request.max_results,
            "output": "json",
        }
    )
    url = f"{ASF_SEARCH_URL}?{params}"
    api_request = urllib.request.Request(
        url,
        headers={"User-Agent": "Ethio-SARs/1.0 (NASA Space Apps demo)"},
    )
    with urllib.request.urlopen(api_request, timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return _flatten_results(payload)


def search_live(request: LiveSarSearchRequest) -> LiveSarSearchResponse:
    """Search NASA ASF for Sentinel-1 GRD and NISAR GCOV scenes.

    The ASF Search API uses different processing levels for the two missions, so
    this function issues one query per mission and merges the normalized results.
    Network and service failures become a clean fallback message.
    """

    wkt = _build_wkt(request.lat, request.lon)
    raw_results: list[dict[str, Any]] = []
    failures: list[str] = []

    for query in ASF_QUERIES:
        try:
            batch = _search_query(
                request,
                wkt,
                query["platform"],
                query["processingLevel"],
            )
            raw_results.extend(batch)
        except Exception as exc:  # noqa: BLE001 - external service boundary
            logger.warning(
                "ASF %s/%s search failed: %s",
                query["platform"],
                query["processingLevel"],
                exc,
            )
            failures.append(f"{query['platform']} {query['processingLevel']}")

    if not raw_results:
        if failures:
            message = (
                "Live NASA ASF search is temporarily unavailable (the service "
                "may be timing out). Please retry in a moment or use the "
                "curated GERD timeline."
            )
        else:
            message = (
                "No Sentinel-1 GRD or NISAR GCOV scenes matched this coordinate "
                "and date window. Try widening the date range."
            )
        return LiveSarSearchResponse(count=0, results=[], message=message)

    results: list[LiveSarScene] = []
    seen: set[str] = set()
    for item in raw_results:
        scene = _normalize_result(item)
        if scene.scene_id in seen:
            continue
        seen.add(scene.scene_id)
        results.append(scene)

    results.sort(
        key=lambda scene: scene.acquisition_time or "",
        reverse=True,
    )
    results = results[: request.max_results]

    message = None
    if failures:
        message = (
            "Some ASF mission queries failed ("
            + ", ".join(failures)
            + "); showing the scenes that were available."
        )

    return LiveSarSearchResponse(
        count=len(results),
        results=results,
        message=message,
    )
