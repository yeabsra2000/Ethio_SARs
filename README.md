# Dancing with the SARs — GERD / Lake Nigat

A working Earth-observation demo for the NASA Space Apps 2026 challenge
**“Dancing with the SARs.”** It turns real Sentinel-1 radar scenes of the Grand
Ethiopian Renaissance Dam (GERD / Lake Nigat) into a 3D map timeline, lets you
compare multiple acquisition years, searches NASA's Alaska Satellite Facility
(ASF) live, and explains radar change with a Gemini + retrieval-augmented
generation (RAG) assistant.

- **Live app (local):** <http://127.0.0.1:8000/>
- **API docs:** <http://127.0.0.1:8000/docs>
- **Source repository:** <https://github.com/yeabsra2000/Ethio_SARs>

> The repository contains the FastAPI backend, the MapLibre frontend, the RAG
> knowledge base, and the four derived SAR overlay PNGs. It deliberately does
> **not** contain the raw Sentinel-1 GeoTIFFs (about 3.2 GB) or the Gemini API
> key.

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

- **A four-date SAR timeline** of the GERD reservoir: 2019, 2021, 2023, and
  2025.
- **Multi-scene map stacking** with per-layer opacity, solo view, and automatic
  playback through the selected years.
- **3D terrain draping** with MapLibre GL JS, satellite or dark basemaps, and a
  hillshade layer.
- **A live NASA ASF search** for Sentinel-1 / NISAR scenes around any point,
  returning scene IDs, footprints, browse images, and download links.
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
| Sensor | Sentinel-1 C-band SAR, IW mode, VV polarization |

---

## Real data, not sample data

The four PNGs served by the app are derived from **real Sentinel-1A
Interferometric Wide (IW) Ground Range Detected (GRD) High-Resolution Level-1
products**, not from the synthetic generator.

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

The water-area numbers in the timeline (48.2, 363, 1100, 1874 km²) are curated
narrative estimates for the demo, not values computed live from the rasters.
See [Accuracy, limits, and attribution](#accuracy-limits-and-attribution).

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

The API already uses the same SDK for its live search. A minimal search looks
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

`clean.py` needs `rasterio`, `numpy`, and `pillow`. The application runtime does
not need `rasterio`; it is only required when regenerating overlays. Install it
if necessary:

```powershell
.\.venv\Scripts\python.exe -m pip install rasterio
```

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

The committed PNGs are about 5.4–7.9 MB each, 2048 × 2048 RGBA, and are served
at `/static/overlays/<filename>`.

---

## Curated timeline

The API timeline is defined in `app/services/gerd_data.py`:

| API ID | Year | Display label | Curated date | Water area | Overlay |
| --- | --- | --- | --- | --- | --- |
| `gerd_2019` | 2019 | Pre-Filling Baseline | 2019-11-15 | 48.2 km² | `/static/overlays/gerd_2019_pre.png` |
| `gerd_2021` | 2021 | First Filling Phase | 2021-11-08 | 363 km² | `/static/overlays/gerd_2021_fill2.png` |
| `gerd_2023` | 2023 | Fourth Filling Phase | 2023-11-02 | 1100 km² | `/static/overlays/gerd_2023_fill4.png` |
| `gerd_2025` | 2025 | Full Reservoir Capacity | 2025-11-10 | 1874 km² | `/static/overlays/gerd_2025_full.png` |

All four source rasters are Sentinel-1A IW GRD VV products. The display dates
are the curated timeline dates; the TIFF tags retain the original product
metadata.

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
│     ├─ gerd_data.py         Curated GERD catalog, bounds, center
│     ├─ asf_client.py        NASA ASF search wrapper and normalizer
│     └─ rag_engine.py        Chunking, embeddings, retrieval, Gemini calls
├─ data/
│  ├─ knowledge_base/
│  │  ├─ sar_physics_guide.md
│  │  └─ gerd_hydrology_timeline.md
│  └─ overlays/
│     ├─ gerd_2019_pre.png
│     ├─ gerd_2021_fill2.png
│     ├─ gerd_2023_fill4.png
│     └─ gerd_2025_full.png
├─ frontend/
│  └─ index.html              Single-page MapLibre mission console
├─ raw_tiffs/                 Original ~790 MB GeoTIFFs (gitignored)
├─ scripts/
│  └─ generate_mock_overlays.py
├─ clean.py                   Sentinel-1 GeoTIFF → map PNG converter
├─ requirements.txt
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

The four overlay PNGs are already committed, so you do **not** need the raw
GeoTIFFs to run the demo.

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
      "overlay_url": "/static/overlays/gerd_2025_full.png",
      "water_area_sq_km": 1874.0,
      "backscatter_summary": "Extensive specular reflection ...",
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
  start_date = "2024-01-01"
  end_date = "2024-12-31"
  max_results = 5
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/sar/search-live `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

The ASF query uses a ~0.1° box around the point, `processingLevel=GRD_HD`, and
Sentinel-1 / NISAR platform filters. It returns normalized results with
`scene_id`, `acquisition_time`, `platform`, `polarization`, `browse_url`,
`download_url`, `bounds`, and `center`. ASF can take 10–30 seconds; failures
return a friendly message instead of a hard error.

---

## RAG / AI explainer

The RAG engine is implemented in `app/services/rag_engine.py`. It has no
external vector database and no database server.

### Knowledge base

Two Markdown documents are loaded at startup:

- `data/knowledge_base/sar_physics_guide.md` — specular reflection, volume
  scattering, double-bounce, and how to read change between dates.
- `data/knowledge_base/gerd_hydrology_timeline.md` — GERD location, reservoir
  scale, filling milestones, and downstream context.

The documents are chunked by headings and paragraphs into **10 chunks** of about
900 characters.

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
- The prompt contains the system instructions, curated scene metadata, the
  retrieved passages, and the user question.
- The model must return JSON with `explanation`, `key_takeaways`, and
  `citations`.
- Generation starts with a 12-second timeout for the lite model and 25 seconds
  for larger fallbacks, with SDK retries disabled so a stalled request cannot
  hang the demo.
- If the primary model fails, the engine tries `gemini-3.5-flash` and then a
  local fallback.
- The local fallback uses the curated scene metadata to explain the water
  change and appends retrieved context.

The result includes `model_used`, `retrieval_mode`, and `fallback_reason` so
the frontend can show exactly what happened.

---

## Frontend and map rendering

`frontend/index.html` is a single-page mission console served at `/` and
`/demo/`.

### Map stack

- **MapLibre GL JS 4.7.1** loaded from unpkg.
- **Esri World Imagery** satellite basemap.
- **CARTO dark** basemap with OSM attribution.
- **AWS Terrain Tiles** (`terrarium` encoding) for 3D terrain.
- A hillshade layer in dark mode.
- The GERD marker, dashed bounds outline, and automatic fit to the analysis
  window.
- Each selected SAR year is a MapLibre `image` source with the same bounds and
  its own raster layer. Opacity, solo, and playback change those layers live.

### Controls

- Click a scene card or checkbox to add/remove it from the stack.
- Per-layer opacity slider and **Solo** button.
- **Play selected** animates through selected years; speed is configurable.
- **Terrain** toggles 3D relief.
- **Satellite / Dark** switches basemaps.
- **Reset** restores the GERD view.
- The AI panel has independent **Before** and **After** selectors, plus
  **First ↔ Last**.
- The ASF panel searches any latitude/longitude and date range, shows browse
  thumbnails, and can zoom the map to a result footprint.

The frontend needs internet access for the MapLibre CDN and map tiles. If the
CDN is blocked, the page shows a map fallback message but the rest of the UI
still works.

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
5. If the new scene changes the hydrology story, update
   `data/knowledge_base/gerd_hydrology_timeline.md` so the RAG answer stays
   grounded.
6. Restart the server and verify:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8000/api/sar/gerd/timeline
   ```

7. Commit only the new PNG and code/metadata changes — **not** the raw TIFF.

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

---

## Accuracy, limits, and attribution

### What is real

- Four real Sentinel-1A IW GRD HR L1 VV scenes.
- Real GCP-based reprojection and contrast stretching in `clean.py`.
- Live NASA ASF metadata search.
- Real Gemini + embedding calls when an API key is configured.

### What is curated or illustrative

- The water-area values (`48.2`, `363`, `1100`, `1874` km²) are curated
  narrative estimates, not live measurements from the rasters.
- The backscatter summaries describe the visual pattern of each scene; they are
  not calibrated geophysical products.
- The 3D terrain is a visualization layer, not a hydraulic or bathymetric
  model.
- The PNG overlays are display images, not analysis-ready radiometric data. Use
  the original GeoTIFFs and a proper SAR processor for quantitative work.

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

### Software and map attribution

- FastAPI and Uvicorn
- MapLibre GL JS
- Esri World Imagery
- OpenStreetMap contributors and CARTO
- AWS Terrain Tiles
- Google Gemini API
- NASA Space Apps Challenge

### License

No license has been selected for this repository yet. Add one before
redistributing or reusing the code commercially.
