"use strict";

const $ = (id) => document.getElementById(id);
const all = (query) => [...document.querySelectorAll(query)];
const icon = (name) => '<svg aria-hidden="true"><use href="#icon-' + name + '"/></svg>';
const formatNumber = new Intl.NumberFormat("en", { maximumFractionDigits: 1 }).format;
const formatDate = (date, options = { dateStyle: "medium" }) =>
  new Date(date + "T00:00:00Z").toLocaleDateString("en", { ...options, timeZone: "UTC" });
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
const safeUrl = (value) => {
  if (!value) return "";
  try {
    const url = new URL(value, window.location.origin);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
};

const state = {
  timeline: null,
  scenes: [],
  selected: new Set(),
  opacity: new Map(),
  masks: new Set(),
  focus: null,
  pair: [],
  nisarPair: [],
  view: "explore",
  playback: null,
  map: null,
  mapReady: false,
  terrain: false,
  basemap: "satellite",
  footprint: null,
};
const findScene = (id) => state.scenes.find((scene) => scene.id === id);
const selectedScenes = () => state.scenes.filter((scene) => state.selected.has(scene.id));

async function api(path, payload, timeout = 15000) {
  try {
    const response = await fetch(path, {
      signal: AbortSignal.timeout(timeout),
      ...(payload && {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }),
    });
    if (!response.ok) {
      const { detail } = await response.json().catch(() => ({}));
      const message = typeof detail === "string" ? detail : detail?.[0]?.msg;
      throw new Error(message || "The server returned HTTP " + response.status + ".");
    }
    return await response.json();
  } catch (error) {
    if (error.name === "TimeoutError") throw new Error("The request timed out. Try again shortly.");
    if (error instanceof TypeError) throw new Error("Could not reach the server. Check the connection and try again.");
    throw error;
  }
}

function openView(view) {
  if (state.view === view) return;
  stopPlayback(false);
  state.view = view;
  document.body.dataset.view = view;
  all("button[data-view]").forEach((button) => {
    const active = button.dataset.view === view;
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
    $(button.dataset.view + "-panel").hidden = !active;
  });
  if (view !== "search" && state.footprint) recenter();
  render();
}

function thumbnail(scene) {
  const filename = scene.overlay_url.split("/").pop().replace(/\.png$/i, ".webp");
  return '/demo/thumbnails/' + encodeURIComponent(filename);
}

function imageMarkup(scene, description = "") {
  return '<img src="' + thumbnail(scene) + '" data-original="' + escapeHtml(safeUrl(scene.overlay_url)) +
    '" alt="' + escapeHtml(description) + '" decoding="async">';
}

function renderTimeline() {
  const selected = state.focus?.id;
  const compare = state.view === "compare";
  $("timeline-help").textContent = compare ? "Choose a scene to set the After date."
    : "Choose a scene or use the checkboxes to stack layers.";
  all(".scene-tile").forEach((tile) => {
    const id = tile.dataset.scene;
    const active = !compare && id === selected;
    const paired = compare && state.pair.includes(id);
    tile.classList.toggle("active", active);
    tile.classList.toggle("paired", paired);
    tile.querySelector("button").setAttribute("aria-pressed", String(active || paired));
    const check = tile.querySelector("input");
    check.hidden = compare;
    check.checked = state.selected.has(id);
  });
  const play = $("play");
  play.disabled = (state.selected.size > 1 ? state.selected.size : state.scenes.length) < 2 || compare;
  play.title = state.selected.size > 1 ? "Play selected scenes" : "Play the full timeline";
  $("speed").disabled = play.disabled;
  play.innerHTML = state.playback ? icon("pause") + "<span>Pause</span>" : icon("play") + "<span>Play</span>";
}

function renderSceneDetails() {
  const scene = state.focus;
  const platform = $("scene-platform");
  platform.hidden = !scene;
  const layers = selectedScenes();
  if (!scene && !state.timeline) return;
  if (scene) {
    platform.dataset.sensor = scene.platform;
    platform.textContent = scene.platform || "SAR";
  }
  const information = scene ? `
    <div class="scene-time">${formatDate(scene.date)}</div>
    <h3>${escapeHtml(scene.label)}</h3>
    <p class="quiet scene-summary">${escapeHtml(scene.backscatter_summary)}</p>
    <dl class="scene-stats">
      <div><dt>Water area estimate</dt><dd>${formatNumber(scene.water_area_sq_km)} <small>km²</small></dd></div>
      <div><dt>Radar band</dt><dd>${escapeHtml(scene.frequency_band || "—")} <small>${escapeHtml(scene.polarization)}</small></dd></div>
    </dl>
    ${scene.area_note ? '<details><summary>How the area was estimated</summary><p>' + escapeHtml(scene.area_note) + '</p></details>' : ''}
    ` : '<p class="quiet">Choose a scene on the timeline or add layers using the checkboxes.</p>';
  const controls = layers.map((layer) => {
    const id = escapeHtml(layer.id);
    const title = formatDate(layer.date);
    const value = state.opacity.get(layer.id);
    return `<div class="layer">
      <div class="layer-head">
        <label for="opacity-${id}">${title} opacity</label>
        <output id="value-${id}" for="opacity-${id}">${value}%</output>
        ${layers.length > 1 ? '<button type="button" class="text-button" data-solo="' + id + '" aria-label="Show only ' + title + '">Solo</button>' : ""}
      </div>
      <input id="opacity-${id}" type="range" min="0" max="100" value="${value}" data-opacity="${id}">
      ${layer.water_mask_url ? '<label class="mask-control"><input type="checkbox" data-mask-toggle="' + id + '"' + (state.masks.has(layer.id) ? " checked" : "") + '> Show water mask</label>' : ""}
    </div>`;
  }).join("");
  $("scene-details").innerHTML = information + `<div class="stack-controls">
    <div class="stack-head"><span class="small-label">MAP LAYERS · ${layers.length}</span>
      <div><button type="button" class="text-button" data-stack="all">Show all</button><button type="button" class="text-button" data-stack="clear">Clear</button></div>
    </div>${controls}</div>`;
}

function activeImages() {
  if (state.view === "compare") {
    const [before, after] = state.pair.map(findScene);
    if (!before || !after) return [];
    const blend = Number($("blend").value) / 100;
    if (before.id === after.id) return [{ scene: before, opacity: 1 }];
    return [{ scene: before, opacity: blend === 1 ? 0 : 1 }, { scene: after, opacity: blend }];
  }
  if (state.playback) return [{ scene: state.focus, opacity: 1 }];
  return selectedScenes().flatMap((scene) => {
    const images = [{ scene, opacity: state.opacity.get(scene.id) / 100 }];
    if (state.masks.has(scene.id) && scene.water_mask_url) images.push({ scene, opacity: 0.85, mask: true });
    return images;
  });
}

function renderMap() {
  const images = activeImages();
  const compare = state.view === "compare";
  const [before, after] = state.pair.map(findScene);
  const focus = state.focus;
  $("map-ident").hidden = compare ? !before || !after : !focus;
  if (compare && before && after) {
    $("map-sensor").textContent = "SCENE COMPARISON";
    $("map-date").textContent = formatDate(before.date) + " → " + formatDate(after.date);
    $("map-caption").textContent = [before.platform, after.platform].filter(Boolean).filter((value, i, list) => list.indexOf(value) === i).join(" / ");
  } else if (focus) {
    $("map-sensor").textContent = [focus.platform, focus.frequency_band, focus.polarization].filter(Boolean).join(" · ").toUpperCase();
    $("map-date").textContent = formatDate(focus.date);
    $("map-caption").textContent = focus.label;
  }
  const prefix = "sar-image-";
  const keyFor = ({ scene, mask }) => prefix + scene.id + (mask ? "-mask" : "");
  const overlayUrl = ({ scene, mask }) => safeUrl(mask ? scene.water_mask_url : scene.overlay_url);
  $("mask-legend").hidden = !images.some((image) => image.mask);
  if (state.timeline) {
    const message = $("map-message");
    message.hidden = images.length > 0 || state.mapReady;
    message.textContent = "Choose a scene from the timeline to preview it here.";
  }
  if (state.mapReady) {
    const map = state.map;
    const desired = new Set(images.map(keyFor));
    const previous = map.getStyle().layers.filter((layer) => layer.id.startsWith(prefix));
    previous.forEach(({ id }) => {
      if (!desired.has(id)) map.setLayoutProperty(id, "visibility", "none");
    });
    images.forEach((image) => {
      const key = keyFor(image);
      if (!map.getSource(key)) {
        const b = image.scene.bounds;
        map.addSource(key, {
          type: "image",
          url: overlayUrl(image),
          coordinates: [[b.west, b.north], [b.east, b.north], [b.east, b.south], [b.west, b.south]],
        });
        map.addLayer({ id: key, type: "raster", source: key, paint: { "raster-fade-duration": 0 } });
      }
      map.setLayoutProperty(key, "visibility", "visible");
      map.setPaintProperty(key, "raster-opacity", image.opacity);
      map.moveLayer(key);
    });
    ["study-outline", "footprint-fill", "footprint-line"].forEach((id) => {
      if (map.getLayer(id)) map.moveLayer(id);
    });
    return;
  }
  const container = $("image-stack");
  const existing = new Map([...container.children].map((element) => [element.dataset.key, element]));
  images.forEach((image, index) => {
    const key = keyFor(image);
    let element = existing.get(key);
    if (!element) {
      element = document.createElement("img");
      element.src = overlayUrl(image);
      element.alt = "";
      element.decoding = "async";
      element.dataset.key = key;
      if (image.mask) element.dataset.mask = "";
      container.append(element);
    }
    element.style.zIndex = index;
    element.style.opacity = image.opacity;
    existing.delete(key);
  });
  existing.forEach((element) => element.remove());
}

function renderPair() {
  const [before, after] = state.pair.map(findScene);
  if (!before || !after) return;
  $("before").value = before.id;
  $("after").value = after.id;
  const preview = $("pair-preview");
  preview.hidden = false;
  preview.innerHTML = imageMarkup(before, "Before · " + formatDate(before.date)) + imageMarkup(after, "After · " + formatDate(after.date));
  const same = before.id === after.id;
  $("blend").disabled = same;
  $("ai-submit").disabled = same || $("ai-form").ariaBusy === "true";
  $("pair-caution").textContent = same ? "Choose two different acquisitions." : before.platform !== after.platform
    ? "These sensors use different wavelengths and polarizations. Compare visual patterns with care."
    : "";
}

function render() {
  renderTimeline();
  $("nisar-action").hidden = state.nisarPair.length !== 2 || !state.nisarPair.every(findScene);
  if (state.view === "explore") renderSceneDetails();
  if (state.view === "compare") renderPair();
  renderMap();
}

function selectScene(scene) {
  if (!scene) return;
  stopPlayback(false);
  if (state.view === "compare") {
    // Timeline selections update the later observation. Both selectors remain independent.
    setPair([state.pair[0], scene.id]);
    return;
  }
  if (state.view === "search") openView("explore");
  state.selected = new Set([scene.id]);
  state.opacity.set(scene.id, 100);
  state.focus = scene;
  render();
}

function setLayer(scene, checked) {
  if (!scene) return;
  stopPlayback(false);
  if (checked) {
    state.opacity.set(scene.id, state.selected.size ? 55 : 100);
    state.selected.add(scene.id);
    state.focus = scene;
  } else {
    state.selected.delete(scene.id);
    if (state.focus?.id === scene.id) state.focus = selectedScenes().at(-1);
  }
  render();
}

function stopPlayback(refresh = true) {
  if (!state.playback) return;
  clearInterval(state.playback.timer);
  state.focus = state.playback.previous;
  state.playback = null;
  if (refresh) render();
}

function startPlayback() {
  if (state.view === "compare") return;
  stopPlayback(false);
  const scenes = state.selected.size > 1 ? selectedScenes() : state.scenes;
  if (scenes.length < 2) return;
  const playback = { previous: state.focus, index: 0 };
  state.playback = playback;
  const advance = () => {
    state.focus = scenes[playback.index];
    playback.index = (playback.index + 1) % scenes.length;
    render();
  };
  advance();
  playback.timer = setInterval(advance, Number($("speed").value));
}

function setPair(ids) {
  state.pair = ids;
  $("ai-result").replaceChildren();
  render();
}

function usePreset(platform) {
  const scenes = state.scenes.filter((scene) => scene.platform === platform);
  if (scenes.length >= 2) setPair([scenes[0].id, scenes.at(-1).id]);
}

function boundsFeature(b) {
  return {
    type: "Feature",
    properties: {},
    geometry: { type: "Polygon", coordinates: [[
      [b.west, b.south], [b.east, b.south], [b.east, b.north], [b.west, b.north], [b.west, b.south],
    ]] },
  };
}

function showBounds(id, bounds) {
  const map = state.map;
  const feature = boundsFeature(bounds);
  const source = map.getSource(id);
  if (source) {
    source.setData(feature);
    return;
  }
  map.addSource(id, { type: "geojson", data: feature });
  const isFootprint = id === "footprint";
  if (isFootprint) map.addLayer({
    id: "footprint-fill", type: "fill", source: id, paint: { "fill-color": "#f2c679", "fill-opacity": 0.16 },
  });
  map.addLayer({
    id: isFootprint ? "footprint-line" : "study-outline", type: "line", source: id,
    paint: { "line-color": isFootprint ? "#f2c679" : "#61e4cf", "line-width": 1.5, "line-dasharray": [3, 2] },
  });
}

function fit(bounds, duration = 0) {
  state.map.fitBounds([[bounds.west, bounds.south], [bounds.east, bounds.north]], {
    padding: 28, maxZoom: 12, duration,
  });
}

function recenter() {
  if (!state.mapReady || !state.timeline) return;
  const map = state.map;
  if (map.getSource("footprint")) {
    map.removeLayer("footprint-line");
    map.removeLayer("footprint-fill");
    map.removeSource("footprint");
  }
  state.footprint = null;
  fit(state.timeline.bounds);
}

function applyTerrain() {
  if (!state.mapReady) return;
  state.map.setTerrain(state.terrain ? { source: "terrain", exaggeration: 1.15 } : null);
  state.map.easeTo({ pitch: state.terrain ? 46 : 0, duration: 400 });
  $("terrain-toggle").setAttribute("aria-pressed", String(state.terrain));
}

function initMap() {
  if (!window.maplibregl || !state.timeline || state.map) return;
  const container = $("map");
  container.hidden = false;
  try {
    const { lon, lat } = state.timeline.center;
    const map = new maplibregl.Map({
      container,
      center: [lon, lat],
      zoom: 9,
      maxPitch: 75,
      cooperativeGestures: true,
      attributionControl: false,
      style: {
        version: 8,
        sources: {
          satellite: {
            type: "raster", tileSize: 256, maxzoom: 19,
            tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
            attribution: "Imagery © Esri, Maxar, Earthstar Geographics",
          },
          terrain: {
            type: "raster-dem", encoding: "terrarium", tileSize: 256, maxzoom: 15,
            tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
            attribution: "Terrain tiles · AWS Open Data",
          },
        },
        layers: [
          { id: "background", type: "background", paint: { "background-color": "#192a34" } },
          { id: "satellite", type: "raster", source: "satellite", paint: { "raster-brightness-max": 0.82, "raster-saturation": -0.15 } },
        ],
      },
    });
    state.map = map;
    container.style.opacity = "0";
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-left");
    map.once("load", () => {
      state.mapReady = true;
      showBounds("study", state.timeline.bounds);
      const popup = new maplibregl.Popup({ offset: 18 }).setText("Lake Nigat observation site");
      new maplibregl.Marker({ color: "#61e4cf", scale: 0.67 }).setLngLat([lon, lat]).setPopup(popup).addTo(map);
      recenter();
      renderMap();
      container.style.opacity = "";
      $("image-stack").hidden = true;
      ["map-tools", "map-settings", "use-center"].forEach((id) => { $(id).hidden = false; });
      $("preview-mode").hidden = true;
      all("[data-footprint]").forEach((button) => { button.hidden = false; });
    });
    map.on("error", ({ sourceId, error }) => {
      if (sourceId?.startsWith("sar-image-")) {
        $("map-message").hidden = false;
        $("map-message").textContent = "A radar layer could not load. Choose another scene or refresh to retry.";
      } else if (sourceId === "terrain" && state.terrain) {
        state.terrain = false;
        applyTerrain();
      }
      console.warn("Radar map:", error?.message || "Map resource unavailable");
    });
  } catch (error) {
    container.hidden = true;
    state.map = null;
    console.warn("Radar preview:", error.message);
  }
}

function dateInput(date) {
  return [date.getFullYear(), String(date.getMonth() + 1).padStart(2, "0"), String(date.getDate()).padStart(2, "0")].join("-");
}

async function loadTimeline() {
  const status = $("timeline-status");
  status.hidden = false;
  status.textContent = "Loading the observation timeline…";
  $("retry").hidden = true;
  try {
    const timeline = await api("/api/sar/gerd/timeline");
    state.scenes = [...timeline.scenes].sort((a, b) => a.date.localeCompare(b.date));
    if (!state.scenes.length) throw new Error("The timeline has no acquisitions.");
    state.timeline = timeline;
    const sentinel = state.scenes.filter((scene) => scene.platform === "Sentinel-1");
    const initial = sentinel.at(-1) || state.scenes.at(-1);
    state.scenes.forEach((scene) => state.opacity.set(scene.id, 55));
    state.opacity.set(initial.id, 100);
    state.focus = initial;
    state.selected.add(initial.id);
    const first = sentinel[0] || state.scenes[0];
    state.pair = [first.id, first.id !== initial.id ? initial.id : state.scenes.at(-1).id];

    $("timeline-list").innerHTML = state.scenes.map((scene) => {
      const id = escapeHtml(scene.id);
      const date = formatDate(scene.date, { month: "short", day: "numeric", year: "numeric" });
      return `<div class="scene-tile" data-scene="${id}">
        <button type="button" data-observation="${id}" title="${escapeHtml(scene.label)}">
          ${imageMarkup(scene)}
          <span class="tile-text"><span class="scene-date">${date}</span><span class="scene-band">${escapeHtml(scene.platform)} · ${escapeHtml(scene.frequency_band?.charAt(0))}</span></span>
        </button>
        <input type="checkbox" class="stack-check" data-layer="${id}" aria-label="Show ${date} in map stack">
      </div>`;
    }).join("");
    const options = state.scenes.map((scene) =>
      `<option value="${escapeHtml(scene.id)}">${formatDate(scene.date)} · ${escapeHtml(scene.platform)}</option>`).join("");
    ["before", "after"].forEach((id) => {
      $(id).innerHTML = options;
      $(id).disabled = false;
    });
    all("[data-pair]").forEach((button) => {
      button.disabled = state.scenes.filter((scene) => scene.platform === button.dataset.pair).length < 2;
    });
    const { lat, lon } = timeline.center;
    $("site-coordinates").textContent = Math.abs(lat).toFixed(3) + "° " + (lat >= 0 ? "N" : "S") + "   " +
      Math.abs(lon).toFixed(3) + "° " + (lon >= 0 ? "E" : "W");
    $("latitude").defaultValue = lat;
    $("longitude").defaultValue = lon;
    status.hidden = true;
    render();
    initMap();
  } catch (error) {
    status.textContent = error.message;
    $("retry").hidden = false;
    $("map-message").textContent = "The radar timeline could not load.";
    $("scene-details").innerHTML = '<p class="quiet">Retry the timeline to load scene details.</p>';
  }
}

async function loadNisar() {
  const details = $("nisar-details");
  try {
    const change = await api("/api/sar/nisar/change");
    state.nisarPair = [change.before.id, change.after.id];
    const formatShort = (date) => formatDate(date, { month: "short", day: "numeric" });
    details.innerHTML = `
      <p class="change-period">${formatShort(change.before.date)} – ${formatDate(change.after.date)} · L-BAND HH</p>
      <p class="change-number">${change.net_change_sq_km > 0 ? "+" : ""}${formatNumber(change.net_change_sq_km)} <small>km²</small></p>
      <p class="quiet">Net water area change</p>
      <dl class="change-details">
        <div><dt>Persistent</dt><dd>${formatNumber(change.persistent_sq_km)} km²</dd></div>
        <div><dt>New water</dt><dd>${formatNumber(change.new_sq_km)} km²</dd></div>
        <div><dt>Lost water</dt><dd>${formatNumber(change.lost_sq_km)} km²</dd></div>
      </dl>
      <details><summary>Method and limitations</summary>
        <p>${escapeHtml(change.method)}</p>
        <p>Common threshold ${escapeHtml(change.threshold_db)} dB${change.jaccard == null ? "" : " · Jaccard overlap " + change.jaccard.toFixed(3)}</p>
        <ul>${change.caveats.map((note) => "<li>" + escapeHtml(note) + "</li>").join("")}</ul>
      </details>`;
    $("nisar-action").hidden = !state.nisarPair.every(findScene);
  } catch {
    details.innerHTML = '<p class="quiet">Calibrated NISAR change data is currently unavailable.</p>';
  }
}

async function loadStatus() {
  const status = $("system-status");
  try {
    await api("/api/health");
    status.dataset.state = "online";
    status.lastElementChild.textContent = "API online";
  } catch {
    status.dataset.state = "offline";
    status.lastElementChild.textContent = "API unavailable";
  }
  try {
    const diagnostics = await api("/api/ai/status");
    $("ai-mode").textContent = diagnostics.gemini_configured ? "Uses Gemini and the local SAR knowledge base."
      : "Uses the local SAR knowledge base.";
  } catch {
    $("ai-mode").textContent = "";
  }
}

function showMessage(container, text, error = false) {
  const message = document.createElement("p");
  message.textContent = text;
  if (error) message.dataset.kind = "error";
  container.replaceChildren(message);
}

async function analyze(event) {
  event.preventDefault();
  const output = $("ai-result");
  const question = $("question").value.trim();
  const [before, after] = state.pair;
  if (!question || !before || !after || before === after) {
    showMessage(output, "Choose two different scenes and enter a question.", true);
    return;
  }
  const form = event.currentTarget;
  form.ariaBusy = "true";
  $("ai-submit").disabled = true;
  showMessage(output, "Analyzing the selected scenes…");
  try {
    const result = await api("/api/ai/analyze-change", {
      before_scene_id: before,
      after_scene_id: after,
      user_question: question,
      location_name: state.timeline.location_name,
    }, 120000);
    if (before !== state.pair[0] || after !== state.pair[1]) return;
    output.innerHTML = `
      <p class="scene-time">${escapeHtml(result.model_used === "local-fallback" ? "Local knowledge base" : result.model_used)}</p>
      <p class="ai-answer">${escapeHtml(result.explanation)}</p>
      ${result.key_takeaways.length ? '<ul>' + result.key_takeaways.map((item) => "<li>" + escapeHtml(item) + "</li>").join("") + '</ul>' : ""}
      ${result.citations.length ? '<details><summary>Sources</summary><ul>' + result.citations.map((item) => "<li>" + escapeHtml(item) + "</li>").join("") + '</ul></details>' : ""}`;
  } catch (error) {
    if (before === state.pair[0] && after === state.pair[1]) showMessage(output, error.message, true);
  } finally {
    form.ariaBusy = "false";
    renderPair();
  }
}

async function search(event) {
  event.preventDefault();
  const output = $("search-result");
  const body = {
    lat: $("latitude").valueAsNumber,
    lon: $("longitude").valueAsNumber,
    start_date: $("start-date").value,
    end_date: $("end-date").value,
    max_results: $("max-results").valueAsNumber,
  };
  if (body.end_date < body.start_date) {
    showMessage(output, "Choose an end date on or after the start date.", true);
    $("end-date").focus();
    return;
  }
  const button = $("search-submit");
  button.disabled = true;
  showMessage(output, "Searching NASA ASF. This may take several seconds…");
  try {
    const data = await api("/api/sar/search-live", body, 90000);
    showMessage(output, data.message || data.count + (data.count === 1 ? " acquisition found." : " acquisitions found."));
    data.results.forEach((scene) => {
      const card = document.createElement("article");
      const browse = safeUrl(scene.browse_url);
      const download = safeUrl(scene.download_url);
      const metadata = [scene.platform, scene.frequency_band, scene.polarization, scene.processing_level].filter(Boolean).join(" · ");
      card.innerHTML = `
        ${browse ? '<img loading="lazy" alt="Radar browse preview" src="' + escapeHtml(browse) + '">' : ""}
        <h3>${escapeHtml(scene.scene_id)}</h3>
        <p>${escapeHtml(metadata)}</p>
        <p>${escapeHtml(scene.acquisition_time?.replace("T", " ").replace(/\.\d+Z$/, "Z"))}</p>
        <div class="result-links">${download ? '<a class="text-button" href="' + escapeHtml(download) + '" target="_blank" rel="noopener noreferrer">Download ↗</a>' : ""}</div>`;
      if (scene.bounds) {
        const footprint = document.createElement("button");
        footprint.type = "button";
        footprint.className = "text-button";
        footprint.dataset.footprint = "";
        footprint.textContent = "View footprint";
        footprint.hidden = !state.mapReady;
        footprint.onclick = () => {
          state.footprint = scene.bounds;
          showBounds("footprint", scene.bounds);
          fit(scene.bounds, 450);
          if (window.matchMedia("(max-width: 760px)").matches) $("map-title").scrollIntoView({ block: "start" });
        };
        card.querySelector(".result-links").append(footprint);
      }
      output.append(card);
    });
  } catch (error) {
    showMessage(output, error.message, true);
  } finally {
    button.disabled = false;
  }
}

function bindEvents() {
  document.addEventListener("error", (event) => {
    const image = event.target;
    if (!(image instanceof HTMLImageElement) || !image.dataset.original) return;
    image.src = image.dataset.original;
    delete image.dataset.original;
  }, true);
  all("button[data-view]").forEach((button) => button.onclick = () => openView(button.dataset.view));
  all("button[data-pair]").forEach((button) => button.onclick = () => usePreset(button.dataset.pair));
  $("timeline-list").addEventListener("click", (event) => {
    const button = event.target.closest("[data-observation]");
    if (button) selectScene(findScene(button.dataset.observation));
  });
  $("timeline-list").addEventListener("change", (event) => {
    const input = event.target;
    if (input.dataset.layer) setLayer(findScene(input.dataset.layer), input.checked);
  });
  $("scene-details").addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.dataset.solo) selectScene(findScene(button.dataset.solo));
    if (button.dataset.stack) {
      stopPlayback(false);
      state.selected = new Set(button.dataset.stack === "all" ? state.scenes.map((scene) => scene.id) : []);
      if (button.dataset.stack === "all") {
        state.scenes.forEach((scene) => state.opacity.set(scene.id, 55));
        state.focus = state.scenes.at(-1);
      } else {
        state.focus = null;
      }
      render();
      $("scene-details").querySelector('[data-stack="' + button.dataset.stack + '"]').focus();
    }
  });
  $("scene-details").addEventListener("input", (event) => {
    const input = event.target;
    if (input.dataset.opacity) {
      state.opacity.set(input.dataset.opacity, Number(input.value));
      if (state.playback) {
        stopPlayback();
        $(input.id).focus({ preventScroll: true });
        return;
      }
      $("value-" + input.dataset.opacity).textContent = input.value + "%";
      renderMap();
    }
  });
  $("scene-details").addEventListener("change", (event) => {
    const input = event.target;
    const id = input.dataset.maskToggle;
    if (!id) return;
    if (input.checked) state.masks.add(id);
    else state.masks.delete(id);
    if (state.playback) {
      stopPlayback();
      $("scene-details").querySelector('[data-mask-toggle="' + CSS.escape(id) + '"]').focus({ preventScroll: true });
      return;
    }
    renderMap();
  });
  $("play").onclick = () => state.playback ? stopPlayback() : startPlayback();
  $("speed").onchange = () => { if (state.playback) startPlayback(); };
  $("before").onchange = () => setPair([$("before").value, state.pair[1]]);
  $("after").onchange = () => setPair([state.pair[0], $("after").value]);
  $("blend").oninput = () => {
    $("blend-value").textContent = $("blend").value + "% after";
    renderMap();
  };
  $("terrain-toggle").onclick = () => {
    state.terrain = !state.terrain;
    applyTerrain();
  };
  all("[data-base]").forEach((button) => button.onclick = () => {
    state.basemap = button.dataset.base;
    const dark = state.basemap === "dark";
    all("[data-base]").forEach((control) => {
      const active = control.dataset.base === state.basemap;
      control.setAttribute("aria-pressed", String(active));
    });
    state.map.setPaintProperty("satellite", "raster-brightness-max", dark ? 0.30 : 0.82);
    state.map.setPaintProperty("satellite", "raster-saturation", dark ? -1 : -0.15);
  });
  $("zoom-in").onclick = () => state.map.zoomIn();
  $("zoom-out").onclick = () => state.map.zoomOut();
  $("reset-map").onclick = recenter;
  $("use-center").onclick = () => {
    const center = state.map.getCenter();
    $("latitude").value = center.lat.toFixed(4);
    $("longitude").value = center.wrap().lng.toFixed(4);
  };
  $("ai-form").onsubmit = analyze;
  $("search-form").onsubmit = search;
  $("compare-nisar").onclick = () => {
    openView("compare");
    setPair(state.nisarPair);
    $("before").focus();
  };
  $("retry").onclick = () => {
    loadTimeline();
    loadNisar();
    loadStatus();
  };
}

const today = new Date();
const earlier = new Date(today);
earlier.setDate(today.getDate() - 45);
$("end-date").value = dateInput(today);
$("start-date").value = dateInput(earlier);
bindEvents();
$("map-library").addEventListener("load", initMap);
loadTimeline();
loadNisar();
loadStatus();
