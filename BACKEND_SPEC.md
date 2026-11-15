# NASA Space Apps 2026: "Dancing with the SARs" — Python Backend Specification

## 1. Project Overview
* **Challenge:** Dancing with the SARs (NASA Space Apps Challenge 2026)
* **Core Focus:** Interactive Synthetic Aperture Radar (SAR) temporal change detection & AI explainer, anchored on a high-impact showcase of the **Grand Ethiopian Renaissance Dam (GERD) / Lake Nigat** (`11.215° N, 35.093° E`), plus a live global coordinate query endpoint.
* **Role of Backend:** Serve pre-processed 2D SAR radar overlays with exact geographic bounding boxes (so the frontend can easily drape them onto a 3D terrain globe like CesiumJS or MapLibre 3D), provide live NASA ASF/NISAR metadata search for custom coordinates, and run a **Google Gemini API** RAG pipeline to explain radar backscatter changes in plain language.

---

## 2. Architecture & Tech Stack
* **Language:** Python 3.11+
* **Web Framework:** `FastAPI` + `uvicorn` (with CORS enabled for frontend integration and automatic OpenAPI/Swagger docs at `/docs`)
* **Satellite Data Search:** NASA ASF Search API (direct HTTP), with mission-specific `Sentinel-1 / GRD_HD` and `NISAR / GCOV` queries; `asf_search` remains an optional SDK for manual exploration.
* **AI & RAG:** `google-genai` (official Google GenAI SDK using `gemini-3.1-flash-lite` for fast reasoning and `gemini-embedding-001` for embeddings) + lightweight `numpy` cosine-similarity store for zero-dependency reliability
* **Geospatial / Image Handling:** `Pillow` (for serving/resizing PNG overlays), `pydantic` (for strict JSON schemas)

---

## 3. Directory Structure
Create the following clean repository layout:

```text
gerd-sar-backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app initialization, CORS, static file mounting
│   ├── config.py            # Environment variables (GEMINI_API_KEY, EARTHDATA_TOKEN)
│   ├── schemas.py           # Pydantic request/response models
│   ├── services/
│   │   ├── gerd_data.py     # Pre-configured GERD multi-year timeline & bounding boxes
│   │   ├── asf_client.py    # Live NASA ASF search wrapper for custom lat/lon/date
│   │   └── rag_engine.py    # Gemini API + local vector store RAG pipeline
│   └── routers/
│       ├── sar.py           # Endpoints for GERD timeline & live SAR search
│       └── ai.py            # Endpoints for AI/RAG explanation & Q&A chat
├── data/
│   ├── overlays/            # Pre-rendered transparent/colorized 2D SAR PNGs for GERD
│   │   ├── gerd_2019_pre.png
│   │   ├── gerd_2021_fill2.png
│   │   ├── gerd_2023_fill4.png
│   │   ├── gerd_2025_full.png
│   │   ├── nisar_2026_10_25.png
│   │   └── nisar_2026_11_06.png
│   └── knowledge_base/      # Markdown/TXT docs for RAG (SAR physics + GERD/NISAR hydrology)
│       ├── sar_physics_guide.md
│       ├── gerd_hydrology_timeline.md
│       └── nisar_gerd_timeline.md
├── scripts/
│   ├── generate_mock_overlays.py  # Generates placeholder SAR PNGs if real ones aren't downloaded yet
│   └── ingest_nisar_browse.py     # NISAR public browse → GERD RGBA overlay
├── LICENSE
├── .env.example
├── requirements.txt
└── README.md
```

---

## 4. 3D Terrain Draping Contract (Frontend <-> Backend)
To render 2D SAR images onto a 3D map (such as **CesiumJS `SingleTileImageryProvider`** or **MapLibre GL `image` source with 3D terrain enabled**) without 3D modeling:
1. Every SAR scene returned by `/api/sar/gerd/timeline` MUST include a standardized `bounds` object:
   * `west`: `34.8500` (Min Longitude)
   * `south`: `10.8500` (Min Latitude)
   * `east`: `35.4500` (Max Longitude)
   * `north`: `11.4500` (Max Latitude)
2. Every scene MUST include a direct `overlay_url` (e.g., `/static/overlays/gerd_2025_full.png`) served via FastAPI `StaticFiles`.
3. The frontend simply passes `overlay_url` and `[west, south, east, north]` into its 3D map engine, which automatically drapes the 2D SAR radar texture over the 3D Blue Nile gorge elevation model.

---

## 5. API Endpoints Specification

### A. `GET /api/health`
* **Purpose:** Health check for deployment platforms (Render/Railway).
* **Response:** `{"status": "ok", "mission": "Dancing with the SARs - GERD"}`

### B. `GET /api/sar/gerd/timeline`
* **Purpose:** Returns the curated multi-year GERD SAR dataset for the frontend before/after comparison slider.
* **Response Schema (`GerdTimelineResponse`):**
  ```json
  {
    "location_name": "Grand Ethiopian Renaissance Dam (Lake Nigat)",
    "center": {"lat": 11.215, "lon": 35.093},
    "bounds": {"west": 34.85, "south": 10.85, "east": 35.45, "north": 11.45},
    "scenes": [
      {
        "id": "gerd_2019",
        "year": 2019,
        "date": "2019-11-15",
        "label": "Pre-Filling Baseline",
        "sensor": "Sentinel-1 C-Band SAR (VV Polarization)",
        "overlay_url": "/static/overlays/gerd_2019_pre.png",
        "water_area_sq_km": 48.2,
        "backscatter_summary": "High radar backscatter across river gorge; narrow natural Blue Nile channel."
      },
      {
        "id": "gerd_2025",
        "year": 2025,
        "date": "2025-11-10",
        "label": "Full Reservoir Capacity",
        "sensor": "Sentinel-1A C-Band SAR (VV Polarization)",
        "overlay_url": "/static/overlays/gerd_2025_full.png",
        "water_area_sq_km": 1874.0,
        "backscatter_summary": "Extensive specular reflection (pitch-black SAR signature) indicating deep standing water across 1,874 sq km."
      },
      {
        "id": "gerd_2026_11_06",
        "year": 2026,
        "date": "2026-11-06",
        "label": "NISAR 12-Day Repeat",
        "sensor": "NISAR L-Band SAR (HH Polarization)",
        "overlay_url": "/static/overlays/nisar_2026_11_06.png",
        "water_area_sq_km": 1043.2,
        "backscatter_summary": "NISAR L-band browse image; low-backscatter reservoir estimate is approximate, not a calibrated water mask."
      }
    ]
  }
  ```

### C. `POST /api/sar/search-live`
* **Purpose:** Live query to NASA's Alaska Satellite Facility (`asf_search`) for any user-selected coordinates and date window on Earth.
* **Request Body (`LiveSarSearchRequest`):**
  ```json
  {
    "lat": 11.215,
    "lon": 35.093,
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "max_results": 5
  }
  ```
* **Implementation Details:**
  * Construct a small WKT polygon buffer (`~0.1°` box around `lat, lon`).
  * Query the ASF Search API twice: `platform=Sentinel-1&processingLevel=GRD_HD` and `platform=NISAR&processingLevel=GCOV`.
  * Merge, deduplicate, sort newest-first, and truncate to `max_results`.
  * Wrap in `try/except` with a clean fallback message if ASF API times out or returns 0 scenes.
  * Return scene ID, acquisition timestamp, platform, frequency band, polarization, processing level, browse image URL, and bounding coordinates.

### D. `POST /api/ai/analyze-change`
* **Purpose:** Triggered automatically when the user moves the frontend before/after slider or asks a question in the chat panel. Uses **Gemini API + RAG** to explain the radar change.
* **Request Body (`AnalyzeChangeRequest`):**
  ```json
  {
    "location_name": "Grand Ethiopian Renaissance Dam (GERD)",
    "before_scene_id": "gerd_2019",
    "after_scene_id": "gerd_2025",
    "user_question": "Why did the center of the image turn completely black and what does this mean for water storage?"
  }
  ```
* **RAG Pipeline Implementation (`app/services/rag_engine.py`):**
  1. On startup, load all `.md` files from `data/knowledge_base/`, chunk by paragraph/section, and embed using `google-genai` (`gemini-embedding-001`). Store vectors in memory (using `numpy`) so no external vector DB server is needed.
  2. At query time, embed `user_question` + scene context, retrieve top 3 relevant chunks via cosine similarity.
  3. Call `client.models.generate_content(model="gemini-3.1-flash-lite", contents=prompt)` with a strict system prompt instructing Gemini to act as an Earth Observation SAR Scientist explaining radar backscatter and NISAR/Sentinel-1 sensor differences clearly to non-experts, citing retrieved facts.
  4. Return structured JSON: `{"explanation": "...", "key_takeaways": ["...", "..."], "citations": ["..."]}`.

---

## 6. Seed Knowledge Base Content (`data/knowledge_base/`)
Have the coding agent populate these two files immediately so the RAG engine works out of the box:
1. **`sar_physics_guide.md`**: Explain Synthetic Aperture Radar (SAR) active microwave sensing, all-weather/cloud-penetrating capability (crucial during Ethiopia's *Kiremt* rainy season), **specular reflection** (smooth calm water reflects radar away -> appears **dark/black**), **volume scattering** (forest canopies -> medium gray), and **double-bounce scattering** (urban structures/dam wall -> bright white).
2. **`gerd_hydrology_timeline.md`**: Summarize GERD location on the Blue Nile (Abay River) in Benishangul-Gumuz, Ethiopia (`11.215° N, 35.093° E`), reservoir capacity (~74 billion cubic meters), surface area (~1,874 sq km at full supply level), and multi-year filling milestones from 2020 through completion.

---

## 7. Instructions for Coding Agent
1. Generate all files listed in Section 3 with clean, type-hinted Python code.
2. Create `requirements.txt` with: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `python-dotenv`, `google-genai`, `numpy`, `asf-search`, `pillow`.
3. Write `scripts/generate_mock_overlays.py` so the backend runs immediately with realistic synthetic dark-water/bright-terrain SAR PNG overlays until real GeoTIFF-to-PNG exports from ASF Vertex are dropped into `data/overlays/`.
4. Enable CORS (`allow_origins=["*"]`) so frontend teammates can call the API from localhost or Vercel without CORS errors.
5. Verify that `uvicorn app.main:app --reload` starts cleanly and `/docs` renders all endpoints.
