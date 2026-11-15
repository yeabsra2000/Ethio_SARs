# Dancing with the SARs — GERD / Lake Nigat

A working Earth-observation demo for the NASA Space Apps 2026 challenge
**“Dancing with the SARs.”** It turns real Sentinel-1 C-band and NISAR L-band
radar scenes of the Grand Ethiopian Renaissance Dam (GERD / Lake Nigat) into a
3D map timeline, lets you compare multiple acquisitions, searches NASA's Alaska
Satellite Facility (ASF) live, and explains radar change with a Gemini +
retrieval-augmented generation (RAG) assistant.

- **Live app (local):** <http://127.0.0.1:8000/>
- **API docs:** <http://127.0.0.1:8000/docs>
- **Source repository:** <https://github.com/yeabsra2000/Ethio_SARs>

> The repository contains the FastAPI backend, the MapLibre frontend, the RAG
> knowledge base, and six derived SAR overlay PNGs (four Sentinel-1 and two
> NISAR). It deliberately does **not** contain the raw Sentinel-1 GeoTIFFs
> (about 3.2 GB), the full NISAR GCOV HDF5 products, or the Gemini API key.

---

## Table of contents

1. [What the project does](#what-the-project-does)
2. [Why GERD](#why-gerd)
3. [Real data, not sample data](#real-data-not-sample-data)
4. [How the data was obtained](#how-the-data-was-obtained)
5. [How the PNG overlays are made](#how-the-png-overlays-are-made)
6. [Curated timeline](#curated-timeline)
7. [Repository layout](#repository-layout)
8. [Quick start](#quick-start)
9. [Configuration](#configuration)
10. [API reference](#api-reference)
11. [RAG / AI explainer](#rag--ai-explainer)
12. [Frontend and map rendering](#frontend-and-map-rendering)
13. [Regenerating data or adding a new year](#regenerating-data-or-adding-a-new-year)
14. [Deployment](#deployment)
15. [Troubleshooting](#troubleshooting)
16. [Accuracy, limits, and attribution](#accuracy-limits-and-attribution)

---

## What the project does

The app answers a simple question: **what happened to the reservoir between
these two radar images, and why does it look that way?**

It provides:

- **A six-date SAR timeline** of the GERD reservoir: four Sentinel-1 C-band
  scenes (2019, 2021, 2023, 2025) and two NISAR L-band scenes (2026).
- **Multi-scene map stacking** with per-layer opacity, solo view, and automatic
  playback through the selected years.
- **3D terrain draping** with MapLibre GL JS, satellite or dark basemaps, and a
  hillshade layer.
- **A live NASA ASF search** for Sentinel-1 GRD and NISAR GCOV scenes around any
  point, returning scene IDs, footprints, browse images, frequency bands, and
  download links.
- **A Gemini + RAG change explainer** that retrieves facts from a local SAR
  knowledge base and answers questions about water, backscatter, and reservoir
  filling.
- **Graceful fallbacks** when the internet, Gemini, or ASF is unavailable, so
  the demo still works offline-ish with local metadata and lexical retrieval.

---

## Why GERD

The Grand Ethiopian Renaissance Dam is on the Blue Nile near the Sudan border.
Its reservoir, Lake Nigat, has filled in stages since 2020. Calm open water is
almost invisible to radar: the surface acts like a mirror and reflects the
Sentinel-1 signal away from the satellite, so water appears **very dark or
black**. Rough terrain, vegetation, and the dam structure scatter energy back
and appear **brighter**. That contrast makes Sentinel-1 a powerful tool for
mapping the growing reservoir through time.

The app uses a fixed analysis window:

| Parameter | Value |
| --- | --- |
| Center | 11.215° N, 35.093° E |
| Bounds | west 34.85°, south 10.85°, east 35.45°, north 11.45° |
| Approx. window size | ~66 km × ~67 km |
| Sensors | Sentinel-1 C-band IW VV; NISAR L-band GCOV HH |

---

## Real data, not sample data

The four Sentinel-1 PNGs served by the app are derived from **real Sentinel-1A
Interferometric Wide (IW) Ground Range Detected (GRD) High-Resolution Level-1
products**, not from the synthetic generator. Two additional NISAR L-band GCOV
scenes cover October and November 2026.

The original files are:

```text
raw_tiffs/gerd_2019_vv.tiff   ~790 MB
raw_tiffs/gerd_2021_vv.tiff   ~790 MB
raw_tiffs/gerd_2023_vv.tiff   ~790 MB
raw_tiffs/gerd_2025_vv.tiff   ~790 MB
```

Metadata read directly from those GeoTIFFs:

| Property | Value |
| --- | --- |
| Product description | `Sentinel-1A IW GRD HR L1` |
| Bands | 1 (VV) |
| Data type | `uint16` |
| Raster size | about 25,225 × 16,793 pixels (varies slightly by scene) |
| CRS / affine transform | **none embedded** |
| Georeferencing | 210 ground control points (GCPs) in `EPSG:4326` |
| GCP footprint | roughly 34.62°–37.19° E, 9.95°–11.90° N |
| Processing software tags | Sentinel-1 IPF 003.10 (2019), 003.40 (2021), 003.71 (2023), 004.00 (2025) |

Because the raw files are huge, they are **ignored by Git** and never uploaded
to GitHub. The derived PNGs under `data/overlays/` are committed instead, so a
fresh clone runs immediately without downloading 3.2 GB of radar data.

> `scripts/generate_mock_overlays.py` still exists as a fallback for machines
> without the raw GeoTIFFs. It creates synthetic dark-water / bright-terrain
> images, but it does **not** overwrite existing real overlays unless you pass
> `--force`. The committed PNGs are the real-data versions.

The Sentinel-1 water-area numbers in the timeline (48.2, 363, 1100, 1874 km²)
are curated narrative estimates for the demo, not values computed live from the
rasters. The two NISAR values (936.6 and 958.5 km²) are calibrated GCOV HH
threshold-based estimates. See
[Accuracy, limits, and attribution](#accuracy-limits-and-attribution).

### NISAR L-band integration

NISAR Level-2 GCOV products are available over GERD. The app uses two
same-track, descending acquisitions about 12 days apart:

| Date | Product ID | Available polarization | Processed | Overlay |
| --- | --- | --- | --- | --- |
| 2026-10-25 | `NISAR_L2_PR_GCOV_034_021_D_083_2005_DHDH_A_20261025T160621_20261025T160656_P05036_N_F_J_001` | HH/HV | HH | `/static/overlays/nisar_2026_10_25_gcov.png` |
| 2026-11-06 | `NISAR_L2_PR_GCOV_035_021_D_083_2005_SHSH_A_20261106T160622_20261106T160656_P05036_N_F_J_001` | HH | HH | `/static/overlays/nisar_2026_11_06_gcov.png` |

The full GCOV HDF5 products are about **1.98 GB** and **1.54 GB** and require a
**NASA Earthdata Login**; an unauthenticated `GET` returns HTTP 401. Set
`EARTHDATA_TOKEN` in `.env`, then download and process with:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_nisar_gcov.py --download
.\.venv\Scripts\python.exe scripts\ingest_nisar_gcov.py --inspect
.\.venv\Scripts\python.exe scripts\ingest_nisar_gcov.py --process
```

Processing uses frequency-A `HHHH` RTC-calibrated gamma0 linear power on a 20 m
UTM grid, converts to dB with `10*log10(HHHH)`, crops to the GERD window, and
applies one common Otsu threshold across both dates (`-14.053 dB`). The resulting
HH water masks are **936.6** and **958.5 km²**. Persistent water is **881.9 km²**,
with **54.7 km² lost** and **76.7 km² new**, a net change of **+21.9 km²** and a
Jaccard overlap of **0.870**. These are calibrated threshold-based estimates, not
independently validated water products. The previous public-browse overlays
remain in `data/overlays/nisar_*.png` as a fallback.

---

## How the data was obtained

The scenes are Sentinel-1A IW GRD High-Resolution Level-1 products in VV
polarization, distributed by **ESA / Copernicus** through **NASA's Alaska
Satellite Facility (ASF)**.

### Option A — ASF Vertex (manual download)

1. Open <https://search.asf.alaska.edu/>.
2. Search around the GERD: **11.215° N, 35.093° E** (or draw a box around
   34.85°–35.45° E, 10.85°–11.45° N).
3. Set the filters:
   - Platform: **Sentinel-1**
   - Processing level: **GRD_HD**
   - Beam mode: **IW**
   - Polarization: **VV**
   - Date range: the year/month you want.
4. Download the GeoTIFF product. If the download contains multiple bands,
   keep the **VV** band (the raw naming in this project is `*_vv.tiff`).
5. Save the four files as:
   - `raw_tiffs/gerd_2019_vv.tiff`
   - `raw_tiffs/gerd_2021_vv.tiff`
   - `raw_tiffs/gerd_2023_vv.tiff`
   - `raw_tiffs/gerd_2025_vv.tiff`

### Option B — `asf_search` Python package

The backend uses the ASF Search API directly, but `asf_search` is still a
convenient way to explore the same catalog. A minimal Sentinel-1 search looks
like this:

```python
import asf_search as asf

wkt = (
    "POLYGON((34.85 10.85, 35.45 10.85, "
    "35.45 11.45, 34.85 11.45, 34.85 10.85))"
)

results = asf.geo_search(
    intersectsWith=wkt,
    platform=asf.PLATFORM.SENTINEL1,
    processingLevel="GRD_HD",
    start="2019-11-01",
    end="2019-11-30",
)

for scene in results:
    props = scene.properties
    print(props.get("sceneName"), props.get("url"))
```

Public ASF metadata search does **not** require an Earthdata login. Downloading
some restricted products may require a NASA Earthdata token; the
`EARTHDATA_TOKEN` setting is reserved for that future use but the current demo
only performs public metadata search.

### Why the TIFFs have no CRS

The products are GeoTIFFs whose geolocation is carried by 210 GCPs rather than
an embedded affine transform. Standard GIS software can display them, but
`rasterio` reports `crs = None`. This is why `clean.py` has an explicit GCP
branch and why the project stores the final map bounds separately in
`app/services/gerd_data.py`.

---

## How the PNG overlays are made

The conversion is done locally by **`clean.py`**. It does not download a
pre-rendered basemap; it transforms the radar raster into a display-ready image.

Pipeline for each scene:

1. **Open the GeoTIFF** and read its GCPs.
2. **Reproject to `EPSG:4326`** with bilinear resampling, using
   `rasterio.warp.calculate_default_transform` and `reproject`.
3. **Crop to the exact GERD bounding box**
   (`34.85, 10.85, 35.45, 11.45`) with a rasterio window.
4. **Convert digital numbers to decibels:**
   `dB = 10 * log10(clip(DN, 1e-6, None))`.
5. **Apply a 2%–98% percentile contrast stretch** on valid pixels, so the
   reservoir and terrain are both visible instead of being dominated by
   outliers.
6. **Mask no-data:** pixels with `DN <= 0` become grayscale 0 and are given
   **transparent alpha** so the satellite basemap can show through the edges.
7. **Resize to at most 2048 × 2048** with Lanczos resampling.
8. **Save an optimized RGBA PNG** under `data/overlays/`.

Run it with:

```powershell
.\.venv\Scripts\python.exe clean.py
```

`clean.py` needs `rasterio`, `numpy`, and `pillow`; the NISAR GCOV script needs
`numpy`, `h5py`, `rasterio`, and `pillow`. Those packages are only needed for
data processing and regeneration, not for serving the committed demo overlays.

### Why the PNGs have no coordinates inside them

The PNG is intentionally a plain image. The geographic placement comes from the
API response: every scene has the same `bounds`, and the frontend passes those
four corners to MapLibre's `image` source:

```js
coordinates: [
  [west, north], [east, north],
  [east, south], [west, south],
]
```

This keeps the data pipeline simple and makes the same PNG usable in MapLibre,
CesiumJS, Leaflet, or a plain `<img>` preview.

The four Sentinel-1 PNGs are about 5.4–7.9 MB each and 2048 × 2048 RGBA. The
calibrated NISAR dB overlays are about 1.3 MB each and 1024 × 1024 RGBA; the
transparent water masks are about 60–70 KB each. All are served at
`/static/overlays/<filename>`.

---

## Curated timeline

The API timeline is defined in `app/services/gerd_data.py`:

| API ID | Year | Display label | Curated date | Sensor | Water area | Overlay |
| --- | --- | --- | --- | --- | --- | --- |
| `gerd_2019` | 2019 | Pre-Filling Baseline | 2019-11-15 | Sentinel-1 C-band VV | 48.2 km² | `/static/overlays/gerd_2019_pre.png` |
| `gerd_2021` | 2021 | First Filling Phase | 2021-11-08 | Sentinel-1 C-band VV | 363 km² | `/static/overlays/gerd_2021_fill2.png` |
| `gerd_2023` | 2023 | Fourth Filling Phase | 2023-11-02 | Sentinel-1 C-band VV | 1100 km² | `/static/overlays/gerd_2023_fill4.png` |
| `gerd_2025` | 2025 | Full Reservoir Capacity | 2025-11-10 | Sentinel-1 C-band VV | 1874 km² | `/static/overlays/gerd_2025_full.png` |
| `gerd_2026_10_25` | 2026 | NISAR L-Band Baseline | 2026-10-25 | NISAR L-band HH GCOV | 936.6 km²* | `/static/overlays/nisar_2026_10_25_gcov.png` |
| `gerd_2026_11_06` | 2026 | NISAR 12-Day Repeat | 2026-11-06 | NISAR L-band HH GCOV | 958.5 km²* | `/static/overlays/nisar_2026_11_06_gcov.png` |

The four Sentinel-1 source rasters are IW GRD VV products. The NISAR rows use
full L2 GCOV HDF5 frequency-A HH gamma0. `*` marks a calibrated threshold-based
water estimate, not an independently validated water product. The display dates
are the curated timeline dates; the original product metadata is retained in the
manifest and knowledge base.

---

## Repository layout

```text
Ethio_SARs/
├─ app/
│  ├─ main.py                 FastAPI app, static mounts, health, lifespan
│  ├─ config.py               Environment settings and paths
│  ├─ schemas.py              Pydantic request/response models
│  ├─ routers/
│  │  ├─ sar.py               Timeline, single scene, live ASF search
│  │  └─ ai.py                Gemini/RAG analysis and status
│  └─ services/
│     ├─ gerd_data.py         Curated GERD catalog, bounds, calibrated NISAR data
│     ├─ asf_client.py        NASA ASF search wrapper and normalizer
│     └─ rag_engine.py        Chunking, embeddings, retrieval, Gemini calls
├─ data/
│  ├─ knowledge_base/
│  │  ├─ sar_physics_guide.md
│  │  ├─ gerd_hydrology_timeline.md
│  │  └─ nisar_gerd_timeline.md
│  ├─ nisar_gcov_manifest.json  Calibrated NISAR masks, areas, change stats
│  └─ overlays/
│     ├─ gerd_2019_pre.png
│     ├─ gerd_2021_fill2.png
│     ├─ gerd_2023_fill4.png
│     ├─ gerd_2025_full.png
│     ├─ nisar_2026_10_25_gcov.png
│     ├─ nisar_2026_10_25_water.png
│     ├─ nisar_2026_11_06_gcov.png
│     ├─ nisar_2026_11_06_water.png
│     ├─ nisar_2026_10_25.png  Legacy public-browse fallback
│     └─ nisar_2026_11_06.png  Legacy public-browse fallback
├─ frontend/
│  ├─ index.html              Lake Nigat Explorer
│  ├─ app.js                  UI state, map layers, and API requests
│  ├─ styles.css              Responsive layout and styling
│  └─ thumbnails/             Lightweight previews of the curated radar scenes
├─ raw_tiffs/                 Original Sentinel-1 GeoTIFFs (gitignored)
│  ├─ nisar_browse/           Public NISAR browse PNG/KML cache (gitignored)
│  └─ nisar_gcov/             Full NISAR GCOV HDF5 cache (gitignored)
├─ scripts/
│  ├─ generate_mock_overlays.py
│  ├─ ingest_nisar_browse.py  Public NISAR browse → RGBA fallback overlay
│  └─ ingest_nisar_gcov.py    Download/inspect/process calibrated NISAR GCOV
├─ clean.py                   Sentinel-1 GeoTIFF → map PNG converter
├─ requirements.txt
├─ LICENSE
├─ .env.example
└─ README.md
```

---

## Quick start

### Requirements

- Python 3.11+ (tested with 3.12)
- Internet access for map tiles, ASF, and Gemini
- Optional: a Google Gemini API key for full AI answers

### Setup

```powershell
git clone https://github.com/yeabsra2000/Ethio_SARs.git
cd Ethio_SARs
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and set GEMINI_API_KEY
```

All eight overlay PNGs are already committed, so you do **not** need the raw
GeoTIFFs or NISAR GCOV cache to run the demo.

### Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then open:

- Mission console: <http://127.0.0.1:8000/>
- API documentation: <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/api/health>

On startup the server loads the knowledge base and builds Gemini embeddings,
which normally takes about 10–20 seconds. The health endpoint is ready after
that warm-up completes.

---

## Configuration

Settings are read from environment variables or `.env` via
`pydantic-settings`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | empty | Google Gemini key. Without it, the AI endpoint uses a local fallback. |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | Primary generation model. |
| `EMBEDDING_MODEL` | `gemini-embedding-001` | Embedding model for the RAG vector store. |
| `RAG_TOP_K` | `3` | Number of knowledge-base chunks retrieved per question. |
| `EARTHDATA_TOKEN` | empty | Reserved for authenticated ASF downloads; public metadata search works without it. |

`.env` is ignored by Git. Never commit a real API key.

```dotenv
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.1-flash-lite
EMBEDDING_MODEL=gemini-embedding-001
RAG_TOP_K=3
```

Model availability depends on your Google AI Studio account. If the configured
model is unavailable, the RAG engine tries other Gemini models and finally
returns a local, metadata-based explanation.

---

## API reference

Base URL: `http://127.0.0.1:8000`

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness check. |
| `GET` | `/api/sar/gerd/timeline` | All curated scenes, bounds, center, overlay URLs. |
| `GET` | `/api/sar/gerd/scenes/{scene_id}` | One curated scene. `404` for unknown IDs. |
| `POST` | `/api/sar/search-live` | Live NASA ASF Sentinel-1 / NISAR search. |
| `POST` | `/api/ai/analyze-change` | Gemini + RAG change explanation. |
| `GET` | `/api/ai/status` | RAG diagnostics: chunks, embeddings, models. |
| `GET` | `/static/overlays/*.png` | Derived SAR overlay images. |
| `GET` | `/demo/` | The frontend (same page as `/`). |

### Timeline

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/sar/gerd/timeline
```

Response shape:

```json
{
  "location_name": "Grand Ethiopian Renaissance Dam (Lake Nigat)",
  "center": {"lat": 11.215, "lon": 35.093},
  "bounds": {"west": 34.85, "south": 10.85, "east": 35.45, "north": 11.45},
  "scenes": [
    {
      "id": "gerd_2025",
      "year": 2025,
      "date": "2025-11-10",
      "label": "Full Reservoir Capacity",
      "sensor": "Sentinel-1A C-Band SAR (VV Polarization)",
      "platform": "Sentinel-1",
      "frequency_band": "C-band",
      "polarization": "VV",
      "product_type": "GRD_HD",
      "overlay_url": "/static/overlays/gerd_2025_full.png",
      "water_area_sq_km": 1874.0,
      "area_note": "Curated narrative estimate ...",
      "backscatter_summary": "Extensive specular reflection ...",
      "bounds": {"west": 34.85, "south": 10.85, "east": 35.45, "north": 11.45}
    },
    {
      "id": "gerd_2026_11_06",
      "year": 2026,
      "date": "2026-11-06",
      "label": "NISAR 12-Day Repeat",
      "sensor": "NISAR L-Band SAR (HH GCOV)",
      "platform": "NISAR",
      "frequency_band": "L-band",
      "polarization": "HH",
      "product_type": "GCOV",
      "data_source": "NISAR L2 GCOV HDF5 frequency-A HHHH gamma0",
      "overlay_url": "/static/overlays/nisar_2026_11_06_gcov.png",
      "water_mask_url": "/static/overlays/nisar_2026_11_06_water.png",
      "water_area_sq_km": 958.5,
      "threshold_db": -14.053,
      "area_note": "Calibrated GCOV HH threshold-based estimate ...",
      "backscatter_summary": "Calibrated NISAR L-band HH ...",
      "bounds": {"west": 34.85, "south": 10.85, "east": 35.45, "north": 11.45}
    }
  ]
}
```

### AI change explanation

```powershell
$body = @{
  before_scene_id = "gerd_2019"
  after_scene_id  = "gerd_2025"
  location_name   = "Grand Ethiopian Renaissance Dam"
  user_question   = "Why did the reservoir turn dark, and what does it mean for water storage?"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/ai/analyze-change `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

Response fields:

- `explanation` — grounded narrative answer.
- `key_takeaways` — 2–4 short bullets.
- `citations` — knowledge-base filenames used.
- `model_used` — Gemini model or `local-fallback`.
- `retrieval_mode` — `vector` or `lexical`.
- `fallback_reason` — set only when the local fallback was used.

### Live ASF search

```powershell
$body = @{
  lat = 11.215
  lon = 35.093
  start_date = "2026-10-01"
  end_date = "2026-11-14"
  max_results = 10
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/sar/search-live `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

The backend queries the ASF Search API directly with a ~0.1° box around the
point. It sends two mission-specific queries because the processing levels
differ: **Sentinel-1 / `GRD_HD`** and **NISAR / `GCOV`**. Results are merged,
deduplicated, sorted newest-first, and normalized with `scene_id`,
`acquisition_time`, `platform`, `frequency_band`, `polarization`,
`processing_level`, `browse_url`, `download_url`, `bounds`, and `center`. ASF
can take 10–30 seconds; failures return a friendly message instead of a hard
error.

---

## RAG / AI explainer

The RAG engine is implemented in `app/services/rag_engine.py`. It has no
external vector database and no database server.

### Knowledge base

Three Markdown documents are loaded at startup:

- `data/knowledge_base/sar_physics_guide.md` — specular reflection, volume
  scattering, double-bounce, and how to read change between dates.
- `data/knowledge_base/gerd_hydrology_timeline.md` — GERD location, reservoir
  scale, filling milestones, and downstream context.
- `data/knowledge_base/nisar_gerd_timeline.md` — NISAR L-band products, full GCOV
  processing, calibrated threshold-based water areas, and 12-day change stats.

The documents are chunked by headings and paragraphs into roughly a dozen chunks
of about 900 characters.

### Retrieval

1. Each chunk is embedded with `gemini-embedding-001` (3072-dimensional
   vectors).
2. Vectors are normalized and kept in memory with NumPy.
3. A user question plus scene metadata is embedded with the
   `RETRIEVAL_QUERY` task type.
4. Cosine similarity selects the top `RAG_TOP_K` chunks (default 3).
5. Query embeddings are cached for repeated demo questions.
6. If embeddings are unavailable, the engine falls back to lexical token
   overlap, so the demo still answers without Gemini.

### Generation

- Primary model: `gemini-3.1-flash-lite`.
- The prompt contains the system instructions, curated scene metadata, computed
  water-area changes, the retrieved passages, and the user question.
- The system prompt explicitly requires a direct answer to the user's question
  and forbids defaulting to a generic SAR tutorial.
- The model must return JSON with `explanation`, `key_takeaways`, and
  `citations`.
- Generation starts with an 18-second timeout for the lite model and 30 seconds
  for larger fallbacks, with SDK retries disabled so a stalled request cannot
  hang the demo.
- If the primary model fails, the engine tries `gemini-3.5-flash` and then a
  local fallback.
- The local fallback is question-aware: it handles greetings, water-capacity
  questions, “which year grew the most” comparisons, and core SAR concepts
  (specular reflection, double-bounce, volume scattering) using curated
  metadata and retrieved context.

The result includes `model_used`, `retrieval_mode`, and `fallback_reason` so
the frontend can show exactly what happened.

---

## Frontend and map rendering

FastAPI serves the Lake Nigat Explorer at `/` and `/demo/`. The frontend uses
HTML, CSS, vanilla JavaScript, and MapLibre GL JS with no Node build step.

- **Explore** opens an acquisition from the timeline. Use its checkbox to add
  it to the map stack. Each layer has its own opacity, and NISAR layers can show
  their water masks. Play cycles through the selected scenes when at least two
  are selected and through the full timeline otherwise.
- **Compare** blends two acquisitions on the map and sends questions about the
  pair to the change explainer. The Sentinel-1 filling and NISAR repeat presets
  select a pair from the same mission. The NISAR summary shows the 12-day net
  change, persistent, new, and lost water, and the threshold and overlap.
- **Search** queries NASA ASF by coordinate and date. Results can include browse
  images, product download links, and a map view of the footprint.

MapLibre drapes each scene within the bounds supplied by FastAPI. Satellite
and Dark use Esri World Imagery, and Terrain uses AWS Terrarium elevation tiles.
The interactive map needs the MapLibre CDN and map tile services. If MapLibre
is unavailable, the explorer displays the locally served radar imagery.

---

## Regenerating data or adding a new year

1. Download a new Sentinel-1A IW GRD HR L1 VV GeoTIFF from ASF (see
   [How the data was obtained](#how-the-data-was-obtained)).
2. Add the source/destination pair to `FILES` in `clean.py`, for example:

   ```python
   FILES = {
       # ...
       "raw_tiffs/gerd_2026_vv.tiff": "data/overlays/gerd_2026_full.png",
   }
   ```

3. Run the converter:

   ```powershell
   .\.venv\Scripts\python.exe clean.py
   ```

4. Add or update the scene in `app/services/gerd_data.py` with the same
   `GERD_BOUNDS`, the new `overlay_url`, year, date, sensor, water-area
   estimate, and a short backscatter summary.
5. If the new scene changes the hydrology story, update the relevant knowledge
   base file (`gerd_hydrology_timeline.md` or `nisar_gerd_timeline.md`) so the
   RAG answer stays grounded.
6. Restart the server and verify:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8000/api/sar/gerd/timeline
   ```

7. Commit only the new PNG and code/metadata changes — **not** the raw TIFF.

### Regenerating the NISAR overlays

The calibrated NISAR GCOV pipeline is standalone:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_nisar_gcov.py --download
.\.venv\Scripts\python.exe scripts\ingest_nisar_gcov.py --inspect
.\.venv\Scripts\python.exe scripts\ingest_nisar_gcov.py --process
```

It downloads the two full frequency-A GCOV HDF5 products into
`raw_tiffs/nisar_gcov/`, reads the `HHHH` gamma0 crop over GERD, computes a
common Otsu threshold, writes `nisar_*_gcov.png` and `nisar_*_water.png`, and
updates `data/nisar_gcov_manifest.json`. Restart the app after regenerating so
the manifest values are reapplied to the timeline. To add another NISAR
acquisition, add its date and product ID to `PRODUCTS` in the script, then add
the scene metadata to `gerd_data.py`.

The public-browse fallback is still available:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_nisar_browse.py --force
```

It downloads the public `LATLON.png` and `.kml` files into
`raw_tiffs/nisar_browse/`, crops to the GERD bounds, and rewrites the two legacy
NISAR overlays. Those values are approximate and are not used by the app unless
the calibrated manifest is removed.

---

## Deployment

GitHub hosts the source, but the FastAPI app needs a Python runtime. GitHub
Pages alone cannot run this backend.

### Render / Railway / Fly.io / a VM

Use these settings:

- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Environment:** set `GEMINI_API_KEY` in the platform's secret manager.
- **Files needed at runtime:** the repository contents; the committed overlay
  PNGs are enough. The raw TIFFs are not needed.
- **Disk:** no database or persistent disk is required.

If your platform uses a different port variable, substitute it in the start
command. For a local production-style run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Troubleshooting

### The AI returns a local fallback

- Check `GEMINI_API_KEY` in `.env` or the deployment environment.
- Open `/api/ai/status`; confirm `gemini_configured`, `embeddings_ready`, and
  `retrieval_mode`.
- If Gemini returns 404, 429, 503, or 504, the configured model may be
  unavailable for your key. Set `GEMINI_MODEL` to a model your account can use.
- Startup may take 10–20 seconds while embeddings are built; a request sent
  before warm-up can be slower.

### “No CRS or GCPs found” in `clean.py`

The input GeoTIFF has neither an embedded CRS nor GCPs. Re-export the product
as a georeferenced VV GeoTIFF, or add a valid GCP set before converting.

### Map is blank or the basemap does not load

- Confirm the CDN is reachable:
  `https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js`.
- Check the browser console for blocked tile requests or a firewall.
- The map tiles (Esri, CARTO, AWS Terrain) all require internet access.

### ASF search is slow or empty

- ASF queries can take 10–30 seconds.
- Widen the date range or check the coordinates.
- If the service is down, the endpoint returns a fallback message and the
  curated timeline remains usable.

### Port 8000 is already in use

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

### Raw TIFFs are missing after cloning

That is expected. They are intentionally excluded from Git. The committed PNGs
let the demo run; download the TIFFs only if you want to regenerate overlays.

### NISAR full product returns HTTP 401

The full GCOV HDF5 products require a NASA Earthdata Login. Set
`EARTHDATA_TOKEN` in `.env` and run `scripts/ingest_nisar_gcov.py --download`.
The public browse PNG/KML remains available through
`scripts/ingest_nisar_browse.py` if full-product access is unavailable.

---

## Accuracy, limits, and attribution

### What is real

- Four real Sentinel-1A IW GRD HR L1 VV scenes.
- Two real NISAR L-band GCOV HDF5 scenes from 2026, processed from the
  frequency-A `HHHH` RTC-calibrated gamma0 layer.
- Real GCP-based reprojection and contrast stretching in `clean.py`, and real
  20 m GCOV cropping, dB conversion, masking, and common Otsu thresholding for
  the NISAR calibrated outputs.
- Live NASA ASF metadata search across Sentinel-1 and NISAR.
- Real Gemini + embedding calls when an API key is configured.

### What is curated or illustrative

- The Sentinel-1 water-area values (`48.2`, `363`, `1100`, `1874` km²) are
  curated narrative estimates, not live measurements from the rasters.
- The NISAR values (`936.6`, `958.5` km²) are calibrated GCOV HH threshold-based
  estimates. They are not independently validated water products and are not
  directly comparable to the Sentinel-1 estimates.
- The NISAR 12-day change (`+21.9 km²` net, Jaccard `0.870`) is threshold- and
  speckle-sensitive; treat small changes as indicative.
- The backscatter summaries describe the visual pattern of each scene; they are
  not calibrated geophysical products.
- The 3D terrain is a visualization layer, not a hydraulic or bathymetric
  model.
- The PNG overlays are display images, not analysis-ready radiometric data. Use
  the original GeoTIFFs or full NISAR GCOV HDF5 products and a proper SAR
  processor for quantitative work.

### Interpretation caveat

Dark radar returns usually mean smooth open water, but shadows, smooth bare
surfaces, and some vegetation can also be dark. Bright returns can come from
rough terrain, buildings, the dam wall, or double-bounce geometry. Always
compare with the original scenes and independent hydrological information
before drawing operational conclusions.

### Data attribution

Contains modified Copernicus Sentinel data (2019–2025), processed by ESA and
accessed through NASA's Alaska Satellite Facility (ASF). Sentinel-1 is a
Copernicus programme mission.

NISAR data are from the NASA-ISRO Synthetic Aperture Radar mission, accessed
through NASA's Alaska Satellite Facility (ASF). The app processes full GCOV HDF5
products downloaded with a NASA Earthdata Login; full GCOV products require
Earthdata credentials.

### Software and map attribution

- FastAPI and Uvicorn
- MapLibre GL JS
- Esri World Imagery
- AWS Terrain Tiles
- Google Gemini API
- NASA Space Apps Challenge

### License

The source code is released under the [MIT License](LICENSE). Satellite data
remain subject to their providers' terms: Copernicus Sentinel data and NASA /
NISAR data are not relicensed by this project.
