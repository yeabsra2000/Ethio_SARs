"""Pydantic request/response models for the public API."""

from datetime import date

from pydantic import BaseModel, Field, field_validator


class Bounds(BaseModel):
    """Geographic bounding box used to drape imagery onto a 3D globe."""

    west: float = Field(..., description="Minimum longitude")
    south: float = Field(..., description="Minimum latitude")
    east: float = Field(..., description="Maximum longitude")
    north: float = Field(..., description="Maximum latitude")


class Center(BaseModel):
    """Scene center coordinates."""

    lat: float
    lon: float


class GerdScene(BaseModel):
    """A curated, pre-rendered GERD SAR overlay."""

    id: str
    year: int
    date: date
    label: str
    sensor: str
    platform: str | None = None
    frequency_band: str | None = None
    polarization: str | None = None
    product_type: str | None = None
    data_source: str | None = None
    overlay_url: str
    water_mask_url: str | None = None
    water_area_sq_km: float
    threshold_db: float | None = None
    area_note: str | None = None
    backscatter_summary: str
    bounds: Bounds


class GerdTimelineResponse(BaseModel):
    """Curated multi-year GERD timeline for the comparison slider."""

    location_name: str
    center: Center
    bounds: Bounds
    scenes: list[GerdScene]


class NisarChangeResponse(BaseModel):
    """Calibrated NISAR GCOV water extent and 12-day change statistics."""

    before: GerdScene
    after: GerdScene
    threshold_db: float
    persistent_sq_km: float
    lost_sq_km: float
    new_sq_km: float
    net_change_sq_km: float
    union_sq_km: float
    jaccard: float | None = None
    method: str
    generated_at: str | None = None
    caveats: list[str] = Field(default_factory=list)


class LiveSarSearchRequest(BaseModel):
    """Live NASA ASF search parameters for an arbitrary location."""

    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    start_date: date
    end_date: date
    max_results: int = Field(default=5, ge=1, le=100)

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, value: date, info) -> date:
        start = info.data.get("start_date")
        if start is not None and value < start:
            raise ValueError("end_date must be on or after start_date")
        return value


class LiveSarScene(BaseModel):
    """Normalized NASA ASF scene metadata."""

    scene_id: str
    acquisition_time: str | None = None
    platform: str | None = None
    frequency_band: str | None = None
    polarization: str | None = None
    processing_level: str | None = None
    browse_url: str | None = None
    download_url: str | None = None
    bounds: Bounds | None = None
    center: Center | None = None


class LiveSarSearchResponse(BaseModel):
    """Response for a live ASF query, including graceful fallbacks."""

    count: int
    results: list[LiveSarScene]
    message: str | None = None


class AnalyzeChangeRequest(BaseModel):
    """Request for a RAG-grounded explanation of a radar change."""

    location_name: str = "Grand Ethiopian Renaissance Dam (GERD)"
    before_scene_id: str
    after_scene_id: str
    user_question: str = Field(..., min_length=1, max_length=2000)


class AnalyzeChangeResponse(BaseModel):
    """Structured Gemini output for the frontend chat panel."""

    explanation: str
    key_takeaways: list[str]
    citations: list[str]
    model_used: str | None = None
    retrieval_mode: str | None = None
    fallback_reason: str | None = None
