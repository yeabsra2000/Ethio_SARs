# Dancing with the SARs — GERD FastAPI Backend

Backend for the NASA Space Apps 2026 challenge **"Dancing with the SARs"**.
It serves curated multi-year SAR overlays of the Grand Ethiopian Renaissance
Dam (GERD / Lake Nigat) with exact bounding boxes for 3D terrain draping, live
NASA ASF scene search, and a Gemini-powered RAG explainer for radar changes.

## Requirements

- Python 3.11+
- A Gemini API key for full AI explanations (optional; a local fallback works
  without one)

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and set GEMINI_API_KEY
```

Generate placeholder SAR overlays if real GeoTIFF exports are not available:

```powershell
python scripts/generate_mock_overlays.py
```

To replace them with real data, place `gerd_20xx_vv.tiff` files in `raw_tiffs/`
and run `python clean.py`, which reprojects and crops them to the GERD bounds.

## Run

```powershell
uvicorn app.main:app --reload
```

- Mission console demo: <http://127.0.0.1:8000/>
- API docs: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/api/health>
- Static overlays: `/static/overlays/gerd_2025_full.png`

The demo page (`frontend/index.html`) includes a MapLibre 3D terrain view with
multi-scene selection, per-layer opacity, timeline playback, live NASA ASF
search, and the Gemini explainer. It is also available at `/demo/`.

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/health` | Liveness check |
| GET | `/api/sar/gerd/timeline` | Curated GERD scenes + `bounds` + `overlay_url` |
| GET | `/api/sar/gerd/scenes/{scene_id}` | Single curated scene |
| POST | `/api/sar/search-live` | Live NASA ASF Sentinel-1 / NISAR search |
| POST | `/api/ai/analyze-change` | Gemini + RAG change explanation |
| GET | `/api/ai/status` | RAG / Gemini diagnostics |

## 3D Draping Contract

Every GERD scene includes:

```json
{
  "bounds": {"west": 34.85, "south": 10.85, "east": 35.45, "north": 11.45},
  "overlay_url": "/static/overlays/gerd_2025_full.png"
}
```

Pass the URL and `[west, south, east, north]` directly to CesiumJS
`SingleTileImageryProvider` or MapLibre GL `image` sources with 3D terrain.

## Project layout

```text
app/
  main.py            FastAPI app, CORS, static mounting
  config.py          Environment settings
  schemas.py         Pydantic models
  services/          GERD catalog, ASF client, RAG engine
  routers/           SAR and AI endpoints
data/
  overlays/          Generated or converted SAR PNG overlays
  knowledge_base/    Markdown documents used by the RAG engine
scripts/
  generate_mock_overlays.py
```
