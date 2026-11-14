"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import (
    DATA_DIR,
    FRONTEND_DIR,
    KNOWLEDGE_BASE_DIR,
    OVERLAYS_DIR,
    get_settings,
)
from app.routers import ai, sar
from app.services.rag_engine import warm_up

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Prepare static directories and warm the RAG engine on startup."""

    OVERLAYS_DIR.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    warm_up()
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Backend for NASA Space Apps 2026 'Dancing with the SARs': curated "
        "GERD/Lake Nigat SAR overlays with 3D draping bounds, live NASA ASF "
        "scene search, and a Gemini-powered SAR explainer."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(DATA_DIR)), name="static")

if FRONTEND_DIR.exists():
    app.mount(
        "/demo",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="demo",
    )

app.include_router(sar.router)
app.include_router(ai.router)


@app.get("/api/health", tags=["Health"], summary="Deployment health check")
def health() -> dict[str, str]:
    """Return a lightweight liveness response."""

    return {"status": "ok", "mission": "Dancing with the SARs - GERD"}


@app.get("/", include_in_schema=False)
def root() -> Response:
    """Serve the mission console demo (fallback to API docs if missing)."""

    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return RedirectResponse(url="/docs")
