"""Gemini + local vector-store RAG pipeline.

The knowledge base is chunked at startup and embedded with Google's
``gemini-embedding-001`` model when a Gemini API key is configured. Vectors are
kept in memory (numpy) so no external vector database is required. When the API
key is absent or embeddings are unavailable, the engine transparently falls back
to a lightweight lexical retriever so the demo still answers out of the box.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.config import KNOWLEDGE_BASE_DIR, get_settings
from app.schemas import AnalyzeChangeRequest, AnalyzeChangeResponse
from app.services.gerd_data import SCENES, get_scene

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency guard
    from google import genai
    from google.genai import types as genai_types
except Exception:  # noqa: BLE001
    genai = None  # type: ignore[assignment]
    genai_types = None  # type: ignore[assignment]

SYSTEM_PROMPT = (
    "You are a synthetic aperture radar (SAR) analyst explaining Sentinel-1 "
    "C-band and NISAR L-band imagery of the Grand Ethiopian Renaissance Dam "
    "(GERD / Lake Nigat) to a non-expert audience. Answer the user's specific "
    "question directly and concisely. Use the supplied scene metadata, computed "
    "water-area changes, and retrieved knowledge-base facts. Do not invent "
    "measurements. Treat NISAR water areas as approximate browse-derived "
    "estimates, not calibrated measurements, and do not present a Sentinel-1 "
    "vs NISAR area change as a like-for-like sensor comparison. Use radar "
    "physics only when it helps answer the question; do not default to a "
    "generic SAR tutorial. If the user greets you, reply in one short sentence "
    "and suggest a concrete GERD/SAR question. If the question is unrelated to "
    "GERD or SAR, briefly say that this assistant focuses on GERD SAR analysis "
    "and redirect. Keep the explanation to 2-5 sentences unless the user asks "
    "for detail. Return JSON with exactly the keys 'explanation' (string), "
    "'key_takeaways' (array of 2-4 strings that directly answer the question), "
    "and 'citations' (array of source filenames actually used)."
)

SENTINEL_SCENES = [scene for scene in SCENES if scene.platform == "Sentinel-1"]
NISAR_SCENES = [scene for scene in SCENES if scene.platform == "NISAR"]

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are",
    "was", "were", "what", "why", "how", "does", "do", "did", "this", "that",
    "with", "from", "as", "at", "by", "it", "its", "be", "been", "has", "have",
    "had", "image", "mean", "means", "can", "could", "would", "should",
}


@dataclass(frozen=True)
class Chunk:
    """A retrievable passage from the knowledge base."""

    text: str
    source: str
    heading: str

    @property
    def label(self) -> str:
        return f"{self.source} - {self.heading}" if self.heading else self.source


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in _STOPWORDS and len(token) > 2
    }


def _load_markdown_documents(directory: Path) -> list[tuple[str, str]]:
    documents: list[tuple[str, str]] = []
    if not directory.exists():
        return documents
    for path in sorted(directory.glob("*")):
        if path.suffix.lower() not in {".md", ".markdown", ".txt"}:
            continue
        try:
            documents.append((path.name, path.read_text(encoding="utf-8")))
        except OSError as exc:  # pragma: no cover - filesystem edge case
            logger.warning("Could not read knowledge-base file %s: %s", path, exc)
    return documents


def _chunk_document(source: str, text: str, target_chars: int = 900) -> list[Chunk]:
    """Chunk markdown/text by section heading and paragraph."""

    chunks: list[Chunk] = []
    heading = "Overview"
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        body = "\n\n".join(part.strip() for part in buffer if part.strip())
        if body:
            chunks.append(Chunk(text=body, source=source, heading=heading))
        buffer = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("#"):
            flush()
            heading = line.lstrip("#").strip() or heading
            continue
        if not line.strip():
            buffer.append("")
            current = "\n\n".join(part for part in buffer if part.strip())
            if len(current) >= target_chars:
                flush()
            continue
        buffer.append(line)

    flush()
    return chunks


class RAGEngine:
    """In-memory retrieval-augmented generation engine for SAR explanations."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._chunks: list[Chunk] = []
        self._embeddings: np.ndarray | None = None
        self._query_cache: dict[str, np.ndarray] = {}
        self._client: Any = None
        self._initialized = False

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    @property
    def embeddings_ready(self) -> bool:
        return self._embeddings is not None and len(self._embeddings) > 0

    @property
    def retrieval_mode(self) -> str:
        """Describe the active retrieval strategy."""

        return "vector" if self.embeddings_ready else "lexical"

    def _model_candidates(self) -> list[str]:
        """Ordered, de-duplicated generation models to try."""

        candidates = [
            self._settings.gemini_model,
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash",
        ]
        seen: set[str] = set()
        ordered: list[str] = []
        for model in candidates:
            if model and model not in seen:
                seen.add(model)
                ordered.append(model)
        return ordered

    def _http_options(self, timeout_ms: int = 30000) -> Any:
        """Fail fast instead of letting the SDK retry for minutes."""

        kwargs: dict[str, Any] = {"timeout": timeout_ms}
        if genai_types is not None and hasattr(genai_types, "HttpRetryOptions"):
            try:
                kwargs["retry_options"] = genai_types.HttpRetryOptions(attempts=1)
            except Exception:  # noqa: BLE001 - older SDKs may differ
                pass
        return genai_types.HttpOptions(**kwargs)

    def _generation_config(self, model: str) -> Any:
        """Build a fast, JSON-only generation config for a specific model."""

        timeout_ms = 18000 if "lite" in model else 30000
        kwargs: dict[str, Any] = {
            "system_instruction": SYSTEM_PROMPT,
            "response_mime_type": "application/json",
            "temperature": 0.2,
            "max_output_tokens": 1400,
            "http_options": self._http_options(timeout_ms),
        }
        if genai_types is not None and hasattr(genai_types, "ThinkingConfig"):
            try:
                kwargs["thinking_config"] = genai_types.ThinkingConfig(
                    thinking_budget=0
                )
            except Exception:  # noqa: BLE001 - older SDKs may not support it
                pass
        return genai_types.GenerateContentConfig(**kwargs)

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if genai is None or not self._settings.gemini_api_key:
            return None
        try:
            self._client = genai.Client(api_key=self._settings.gemini_api_key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not initialize Gemini client: %s", exc)
            self._client = None
        return self._client

    def initialize(self) -> None:
        """Load and chunk documents, then embed them when possible."""

        if self._initialized:
            return
        self._initialized = True

        documents = _load_markdown_documents(KNOWLEDGE_BASE_DIR)
        chunks: list[Chunk] = []
        for source, text in documents:
            chunks.extend(_chunk_document(source, text))
        self._chunks = chunks
        logger.info("Loaded %d knowledge-base chunks", len(self._chunks))

        if not self._chunks:
            return

        self._build_embeddings()

    def _embed_texts(self, texts: list[str]) -> np.ndarray | None:
        client = self._get_client()
        if client is None or genai_types is None:
            return None
        try:
            response = client.models.embed_content(
                model=self._settings.embedding_model,
                contents=texts,
                config=genai_types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    http_options=self._http_options(),
                ),
            )
        except Exception as exc:  # noqa: BLE001 - retry without optional config
            logger.info("Embedding with task_type config failed (%s); retrying", exc)
            try:
                response = client.models.embed_content(
                    model=self._settings.embedding_model,
                    contents=texts,
                    config=genai_types.EmbedContentConfig(
                        http_options=self._http_options()
                    ),
                )
            except Exception as retry_exc:  # noqa: BLE001
                logger.warning("Gemini embedding request failed: %s", retry_exc)
                return None

        embeddings = getattr(response, "embeddings", None)
        if not embeddings:
            return None
        try:
            matrix = np.asarray(
                [embedding.values for embedding in embeddings], dtype=np.float32
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Malformed embedding response: %s", exc)
            return None
        if matrix.ndim != 2 or matrix.shape[0] != len(texts):
            return None
        return matrix

    def _build_embeddings(self) -> None:
        matrix = self._embed_texts([chunk.text for chunk in self._chunks])
        if matrix is None:
            logger.info("Embeddings unavailable; using lexical retrieval fallback")
            return
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._embeddings = matrix / norms
        logger.info("Embedded %d knowledge-base chunks", len(self._chunks))

    def _embed_query(self, query: str) -> np.ndarray | None:
        if not self.embeddings_ready:
            return None
        cache_key = query.strip().lower()
        cached = self._query_cache.get(cache_key)
        if cached is not None:
            return cached
        client = self._get_client()
        if client is None or genai_types is None:
            return None
        try:
            response = client.models.embed_content(
                model=self._settings.embedding_model,
                contents=[query],
                config=genai_types.EmbedContentConfig(
                    task_type="RETRIEVAL_QUERY",
                    http_options=self._http_options(8000),
                ),
            )
        except Exception:  # noqa: BLE001
            try:
                response = client.models.embed_content(
                    model=self._settings.embedding_model,
                    contents=[query],
                    config=genai_types.EmbedContentConfig(
                        http_options=self._http_options(8000)
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Query embedding failed: %s", exc)
                return None

        embeddings = getattr(response, "embeddings", None)
        if not embeddings:
            return None
        vector = np.asarray(embeddings[0].values, dtype=np.float32)
        norm = float(np.linalg.norm(vector))
        vector = vector / norm if norm else vector
        if len(self._query_cache) >= 64:
            self._query_cache.pop(next(iter(self._query_cache)))
        self._query_cache[cache_key] = vector
        return vector

    def _retrieve(self, query: str, k: int) -> list[Chunk]:
        if not self._chunks:
            self.initialize()
        if not self._chunks:
            return []

        k = min(k, len(self._chunks))
        query_vector = self._embed_query(query)
        if query_vector is not None and self._embeddings is not None:
            similarities = self._embeddings @ query_vector
            order = np.argsort(-similarities)[:k]
            return [self._chunks[int(index)] for index in order]

        query_tokens = _tokenize(query)
        scored: list[tuple[float, Chunk]] = []
        for chunk in self._chunks:
            chunk_tokens = _tokenize(f"{chunk.heading} {chunk.text}")
            overlap = len(query_tokens & chunk_tokens)
            if overlap == 0:
                continue
            score = overlap / (len(query_tokens) or 1)
            scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        if not scored:
            return self._chunks[:k]
        return [chunk for _, chunk in scored[:k]]

    def _scene_context(self, request: AnalyzeChangeRequest) -> str:
        lines = [f"Location: {request.location_name}"]
        for role, scene_id in (
            ("Before", request.before_scene_id),
            ("After", request.after_scene_id),
        ):
            scene = get_scene(scene_id)
            if scene is None:
                lines.append(f"{role} scene: {scene_id} (not in curated catalog)")
                continue
            lines.append(
                f"{role} scene: {scene.id} | {scene.date.isoformat()} | "
                f"{scene.label} | sensor: {scene.sensor} | "
                f"platform: {scene.platform or 'n/a'} | "
                f"band: {scene.frequency_band or 'n/a'} | "
                f"polarization: {scene.polarization or 'n/a'} | "
                f"product: {scene.product_type or 'n/a'} | "
                f"water area: {scene.water_area_sq_km} sq km"
                + (f" | area note: {scene.area_note}" if scene.area_note else "")
                + f" | backscatter: {scene.backscatter_summary}"
            )

        lines.append("Curated timeline for all years:")
        for scene in SCENES:
            lines.append(
                f"- {scene.id} | {scene.date.isoformat()} | {scene.label} | "
                f"{scene.platform or 'platform n/a'} {scene.frequency_band or ''} | "
                f"water area: {scene.water_area_sq_km} sq km"
            )

        if SENTINEL_SCENES and NISAR_SCENES:
            lines.append(
                "Sensor note: Sentinel-1 is C-band VV; NISAR is L-band HH/HV. "
                "The NISAR overlays come from public browse PNGs because the full "
                "GCOV HDF5 products require a NASA Earthdata Login. NISAR water "
                "areas are Otsu low-backscatter estimates, not calibrated masks, "
                "so compare them qualitatively with the Sentinel-1 timeline."
            )

        if len(SCENES) > 1:
            lines.append("Computed water-area changes between consecutive scenes:")
            intervals: list[tuple[float, Any, Any]] = []
            for previous, current in zip(SCENES, SCENES[1:]):
                delta = current.water_area_sq_km - previous.water_area_sq_km
                intervals.append((delta, previous, current))
                direction = "increased" if delta >= 0 else "decreased"
                lines.append(
                    f"- {previous.date.isoformat()} to {current.date.isoformat()}: "
                    f"{direction} by {abs(delta):,.1f} sq km"
                )
            largest = max(intervals, key=lambda item: item[0])
            lines.append(
                "Largest increase between consecutive curated scenes: "
                f"{largest[1].date.isoformat()} to {largest[2].date.isoformat()} "
                f"(+{largest[0]:,.1f} sq km)."
            )

        return "\n".join(lines)

    def _build_fallback(
        self, request: AnalyzeChangeRequest, chunks: list[Chunk], reason: str,
    ) -> AnalyzeChangeResponse:
        before = get_scene(request.before_scene_id)
        after = get_scene(request.after_scene_id)
        question = request.user_question.strip()
        lower = question.lower()
        citations = sorted({chunk.source for chunk in chunks})

        if re.match(
            r"^(hi|hello|hey|yo|selam|salam|good\s+(morning|afternoon|evening))\b",
            lower,
        ):
            return AnalyzeChangeResponse(
                explanation=(
                    "Hello! I can explain the GERD radar timeline, compare two "
                    "filling years, or describe what a dark or bright SAR "
                    "signature means. For example, ask: “Which year had the "
                    "largest water-area increase?”"
                ),
                key_takeaways=[
                    "Ask about a specific year or a SAR feature to get a focused answer.",
                    "The local fallback is active; add a Gemini key for full narrative answers.",
                ],
                citations=[],
                model_used="local-fallback",
                retrieval_mode=self.retrieval_mode,
                fallback_reason=reason,
            )

        if before and after:
            delta = after.water_area_sq_km - before.water_area_sq_km
            direction = "increased" if delta >= 0 else "decreased"

            if any(
                token in lower
                for token in ("largest", "biggest", "which year", "most increase")
            ):
                intervals: list[tuple[float, Any, Any]] = [
                    (
                        current.water_area_sq_km - previous.water_area_sq_km,
                        previous,
                        current,
                    )
                    for previous, current in zip(SCENES, SCENES[1:])
                ]
                largest = max(intervals, key=lambda item: item[0])
                sentinel_first = SENTINEL_SCENES[0] if SENTINEL_SCENES else SCENES[0]
                sentinel_last = SENTINEL_SCENES[-1] if SENTINEL_SCENES else SCENES[-1]
                explanation = (
                    f"The largest mapped water-area increase between consecutive "
                    f"curated scenes is from {largest[1].date.isoformat()} to "
                    f"{largest[2].date.isoformat()}: "
                    f"+{largest[0]:,.1f} sq km. Across the Sentinel-1 timeline, "
                    f"surface water grows from {sentinel_first.water_area_sq_km:,} "
                    f"sq km to {sentinel_last.water_area_sq_km:,} sq km, an overall "
                    f"increase of "
                    f"{sentinel_last.water_area_sq_km - sentinel_first.water_area_sq_km:,.1f} "
                    f"sq km. The later NISAR L-band scenes are an approximate "
                    f"cross-sensor check, not part of that Sentinel-1 total."
                )
                takeaways = [
                    f"Largest interval gain: +{largest[0]:,.1f} sq km "
                    f"({largest[1].year} to {largest[2].year}).",
                    "The dark reservoir signature grows because calm water "
                    "reflects radar energy away from the satellite.",
                ]
            elif any(
                token in lower
                for token in ("capacity", "water volume", "hold", "cubic", "km3", "km³")
            ):
                sentinel_first = SENTINEL_SCENES[0] if SENTINEL_SCENES else SCENES[0]
                sentinel_last = SENTINEL_SCENES[-1] if SENTINEL_SCENES else SCENES[-1]
                explanation = (
                    "At full supply level the GERD reservoir is designed to hold "
                    "roughly 74 billion cubic metres (74 km³) of water, with a "
                    "surface area of about 1,874 sq km. The curated Sentinel-1 "
                    "timeline shows the surface-water signal expanding from "
                    f"{sentinel_first.water_area_sq_km:,} sq km in "
                    f"{sentinel_first.year} to "
                    f"{sentinel_last.water_area_sq_km:,} sq km in "
                    f"{sentinel_last.year}."
                )
                takeaways = [
                    "Design storage at full supply level: about 74 km³.",
                    "Full-supply surface area: about 1,874 sq km.",
                ]
            elif any(
                token in lower
                for token in ("nisar", "l-band", "l band", "lband")
            ):
                nisar_dates = ", ".join(
                    scene.date.isoformat() for scene in NISAR_SCENES
                )
                nisar_areas = ", ".join(
                    f"{scene.water_area_sq_km:,.0f} sq km" for scene in NISAR_SCENES
                )
                explanation = (
                    "NISAR is the NASA-ISRO L-band SAR mission, and its longer "
                    "wavelength penetrates vegetation and responds to soil "
                    "moisture and biomass more than Sentinel-1 C-band. The GERD "
                    "timeline includes NISAR GCOV scenes from "
                    f"{nisar_dates}, acquired on the same track about 12 days "
                    "apart. The app uses the public NISAR browse images because "
                    "the full GCOV HDF5 products need a NASA Earthdata Login; the "
                    "browse-derived low-backscatter areas are about "
                    f"{nisar_areas}, but they are approximate and not calibrated "
                    "water masks."
                )
                takeaways = [
                    "NISAR adds L-band HH/HV observations to the C-band Sentinel-1 timeline.",
                    "The two NISAR scenes are a 12-day repeat over the same GERD track.",
                    "NISAR browse-derived areas are approximate, not like-for-like water measurements.",
                ]
            elif any(
                token in lower
                for token in ("sentinel-1", "sentinel 1", "c-band", "c band")
            ):
                sentinel_first = SENTINEL_SCENES[0] if SENTINEL_SCENES else SCENES[0]
                sentinel_last = SENTINEL_SCENES[-1] if SENTINEL_SCENES else SCENES[-1]
                explanation = (
                    "Sentinel-1 is ESA's C-band SAR mission, and the curated "
                    "timeline uses VV-polarized GRD scenes to track the reservoir "
                    f"from {sentinel_first.date.isoformat()} to "
                    f"{sentinel_last.date.isoformat()}. The mapped surface-water "
                    f"area grows from {sentinel_first.water_area_sq_km:,} sq km to "
                    f"{sentinel_last.water_area_sq_km:,} sq km over that period. "
                    "The newer NISAR L-band scenes are a complementary check, not "
                    "a direct replacement for the C-band series."
                )
                takeaways = [
                    "Sentinel-1 C-band VV provides the long 2019-2025 GERD record.",
                    "The reservoir's dark specular signature expands as it fills.",
                    "NISAR L-band adds a complementary longer-wavelength view.",
                ]
            elif any(
                token in lower
                for token in ("double-bounce", "double bounce", "corner reflector")
            ):
                explanation = (
                    "Double-bounce scattering happens when a radar pulse hits two "
                    "perpendicular surfaces, such as the ground and a vertical "
                    "wall, and bounces back toward the satellite. That strong "
                    "return makes the GERD dam wall, steep rocky banks, and other "
                    "angular structures appear bright white, while calm water "
                    "beyond them stays dark."
                )
                takeaways = [
                    "Double-bounce needs two surfaces at roughly a right angle.",
                    "The dam wall and steep banks are bright because of it.",
                ]
            elif any(
                token in lower
                for token in ("specular", "why is the water dark", "look dark")
            ):
                explanation = (
                    "Calm water is dark in SAR because the surface acts like a "
                    "mirror: the radar pulse reflects away from the satellite "
                    "instead of returning to it. That low backscatter is why the "
                    "growing GERD reservoir shows up as a large black region, "
                    "while rough terrain and the dam structure return more energy "
                    "and appear brighter."
                )
                takeaways = [
                    "Specular reflection makes smooth water look black.",
                    "The reservoir's dark area grows as filling expands.",
                ]
            elif "volume scattering" in lower:
                explanation = (
                    "Volume scattering occurs when the radar pulse penetrates "
                    "vegetation or a rough surface and bounces multiple times "
                    "inside it. The energy that eventually returns to the "
                    "satellite produces a medium-gray tone, which is why vegetated "
                    "and rough terrain around the reservoir is brighter than calm "
                    "water."
                )
                takeaways = [
                    "Volume scattering produces medium-gray returns.",
                    "It contrasts with the dark specular return from open water.",
                ]
            else:
                explanation = (
                    f"You asked about the GERD change from "
                    f"{before.date.isoformat()} to {after.date.isoformat()}. "
                    f"The curated surface-water area {direction} by about "
                    f"{abs(delta):,.1f} sq km "
                    f"(from {before.water_area_sq_km:,} to "
                    f"{after.water_area_sq_km:,} sq km). Calm open water appears "
                    "dark in SAR because it reflects the radar pulse away from the "
                    "sensor; rough terrain, vegetation, and the dam structure "
                    "appear brighter."
                )
                takeaways = [
                    f"Surface water {direction} by roughly {abs(delta):,.1f} sq km "
                    f"between {before.year} and {after.year}.",
                    "Dark pixels are specular reflection from smooth water, not "
                    "missing data.",
                    "Bright edges trace steep banks, vegetation, and dam "
                    "infrastructure.",
                ]
                if (
                    before.platform
                    and after.platform
                    and before.platform != after.platform
                ):
                    explanation += (
                        " This comparison crosses sensors "
                        f"({before.platform} {before.frequency_band or ''} vs "
                        f"{after.platform} {after.frequency_band or ''}), so treat "
                        "the area difference as an indicative visual comparison "
                        "rather than a calibrated like-for-like measurement."
                    )
        else:
            explanation = (
                "The selected scenes are not both in the curated GERD catalog. "
                "Choose two timeline scenes for a water-area comparison. In "
                "general, smooth open water appears dark in SAR, while rough "
                "terrain and built structures appear brighter."
            )
            takeaways = [
                "Choose two curated scenes to compare water-area changes.",
                "Dark SAR returns usually indicate smooth water surfaces.",
            ]

        if chunks and not any(
            token in lower
            for token in (
                "largest",
                "biggest",
                "which year",
                "capacity",
                "double-bounce",
                "double bounce",
                "specular",
                "volume scattering",
                "look dark",
                "nisar",
                "l-band",
                "l band",
                "sentinel-1",
                "sentinel 1",
                "c-band",
                "c band",
            )
        ):
            explanation += (
                "\n\nRelevant knowledge-base context: "
                + " ".join(
                    chunk.text.strip().replace("\n", " ") for chunk in chunks[:1]
                )
            )

        return AnalyzeChangeResponse(
            explanation=explanation,
            key_takeaways=takeaways,
            citations=citations,
            model_used="local-fallback",
            retrieval_mode=self.retrieval_mode,
            fallback_reason=reason,
        )

    @staticmethod
    def _parse_model_json(text: str) -> dict[str, Any] | None:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            payload = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def analyze_change(self, request: AnalyzeChangeRequest) -> AnalyzeChangeResponse:
        """Retrieve context and produce a grounded explanation."""

        self.initialize()
        scene_context = self._scene_context(request)
        retrieval_query = f"{request.user_question}\n{scene_context}"
        chunks = self._retrieve(retrieval_query, self._settings.rag_top_k)

        client = self._get_client()
        if client is None:
            return self._build_fallback(
                request,
                chunks,
                "Gemini is not configured; set GEMINI_API_KEY to enable the "
                "full AI explanation.",
            )

        context_text = "\n\n".join(
            f"[{chunk.label}]\n{chunk.text}" for chunk in chunks
        ) or "(no knowledge-base passages retrieved)"

        prompt = (
            f"REFERENCE DATA (do not repeat this verbatim):\n{scene_context}\n\n"
            f"RETRIEVED KNOWLEDGE BASE:\n{context_text}\n\n"
            f"USER QUESTION:\n{request.user_question}\n\n"
            "Answer the USER QUESTION above directly. Do not answer a different "
            "question and do not paste a generic SAR primer. If the question is "
            "a greeting, respond briefly and suggest one concrete GERD/SAR "
            "question. Return only the JSON object."
        )

        raw_text = ""
        used_model: str | None = None
        last_error: Exception | None = None
        for model in self._model_candidates():
            started = time.perf_counter()
            try:
                config = self._generation_config(model)
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                candidate = getattr(response, "text", None) or ""
                if candidate.strip():
                    raw_text = candidate
                    used_model = model
                    logger.info(
                        "Gemini model %s answered in %.2fs", model,
                        time.perf_counter() - started,
                    )
                    break
                last_error = RuntimeError(f"{model} returned empty text")
            except Exception as exc:  # noqa: BLE001 - external service boundary
                last_error = exc
                logger.warning(
                    "Gemini model %s failed after %.2fs: %s", model,
                    time.perf_counter() - started, exc,
                )

        if not raw_text:
            logger.warning("All Gemini generation models failed: %s", last_error)
            return self._build_fallback(
                request,
                chunks,
                "the Gemini request failed; showing a local summary.",
            )

        payload = self._parse_model_json(raw_text)
        if payload is None:
            return AnalyzeChangeResponse(
                explanation=raw_text.strip(),
                key_takeaways=[
                    "Dark SAR signatures over calm water indicate specular "
                    "reflection.",
                    "Brighter surroundings indicate rough terrain or structures.",
                ],
                citations=sorted({chunk.source for chunk in chunks}),
                model_used=used_model,
                retrieval_mode=self.retrieval_mode,
            )

        explanation = str(payload.get("explanation") or "").strip()
        takeaways = payload.get("key_takeaways") or []
        citations = payload.get("citations") or []

        if isinstance(takeaways, str):
            takeaways = [takeaways]
        if isinstance(citations, str):
            citations = [citations]

        if not explanation:
            return self._build_fallback(
                request, chunks, "Gemini returned no explanation text."
            )

        return AnalyzeChangeResponse(
            explanation=explanation,
            key_takeaways=[str(item) for item in takeaways][:4],
            citations=[str(item) for item in citations]
            or sorted({chunk.source for chunk in chunks}),
            model_used=used_model,
            retrieval_mode=self.retrieval_mode,
        )


rag_engine = RAGEngine()


def warm_up() -> None:
    """Best-effort startup hook for knowledge-base loading and embedding."""

    try:
        rag_engine.initialize()
    except Exception as exc:  # noqa: BLE001 - never block API startup
        logger.warning("RAG warm-up failed: %s", exc)


def get_engine_status() -> dict[str, Any]:
    """Expose lightweight RAG diagnostics for health checks."""

    return {
        "knowledge_base_chunks": rag_engine.chunk_count,
        "embeddings_ready": rag_engine.embeddings_ready,
        "gemini_configured": bool(get_settings().gemini_api_key),
        "retrieval_mode": rag_engine.retrieval_mode,
        "generation_model": get_settings().gemini_model,
        "embedding_model": get_settings().embedding_model,
    }
