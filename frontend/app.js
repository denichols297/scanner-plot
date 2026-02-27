/* ============================================================
   app.js — Scanner Plot Frontend Logic
   Leaflet map, Socket.IO client, call list, interactions
   ============================================================ */
'use strict';

// ── Configuration ─────────────────────────────────────────────────────────
const MAP_CENTER = [43.235, -75.398]; // Oneida County, NY centroid
const MAP_ZOOM = 10;
const BACKEND_URL = window.location.origin; // same host as Flask

// ── Icon definitions ─────────────────────────────────────────────────────
const CALL_ICONS = {
    fire: { emoji: '🔥', label: 'Fire' },
    police: { emoji: '🚔', label: 'Police' },
    medical: { emoji: '🚑', label: 'Medical' },
    other: { emoji: '⚠️', label: 'Other' },
};

// ── State ─────────────────────────────────────────────────────────────────
let callCount = 0;
let activeCallId = null;
/**
 * Map from call ID → { marker: L.Marker, cardEl: HTMLElement, markerEl: HTMLElement }
 * @type {Map<string, {marker: any, cardEl: HTMLElement, markerEl: HTMLElement}>}
 */
const callRegistry = new Map();

// ── Helpers ───────────────────────────────────────────────────────────────
function formatTime(isoString) {
    const d = new Date(isoString);
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');
    return `${hh}:${mm}:${ss}`;
}

function formatTimestamp(isoString) {
    return new Date(isoString).toLocaleString('en-US', {
        month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: false,
    });
}

function createMarkerIcon(type) {
    const icon = CALL_ICONS[type] || CALL_ICONS.other;
    const el = document.createElement('div');
    el.className = `map-marker ${type}`;
    el.innerHTML = `<span>${icon.emoji}</span>`;
    return el;
}

// ── Map Initialization ────────────────────────────────────────────────────
const map = L.map('map', {
    center: MAP_CENTER,
    zoom: MAP_ZOOM,
    zoomControl: false,
});

// Dark tile layer (CartoDB Dark Matter)
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 19,
}).addTo(map);

// Custom zoom control position
L.control.zoom({ position: 'bottomright' }).addTo(map);

// ── Live Clock ─────────────────────────────────────────────────────────────
const clockEl = document.getElementById('clock');

function updateClock() {
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    const ss = String(now.getSeconds()).padStart(2, '0');
    clockEl.textContent = `${hh}:${mm}:${ss}`;
}
updateClock();
setInterval(updateClock, 1000);

// ── Status Bar ─────────────────────────────────────────────────────────────
const feedDotEl = document.getElementById('feedDot');
const feedLabelEl = document.getElementById('feedLabel');
const callCountEl = document.getElementById('callCount');

function updateStatus(state, mode) {
    feedDotEl.className = `feed-dot ${state}`;

    const labels = {
        demo: '🟡 Demo Mode',
        connected: '🟢 Connected',
        connecting: '🔵 Connecting…',
        disconnected: '🔴 Disconnected',
        error: '🔴 Error — Retrying',
    };
    feedLabelEl.textContent = labels[state] || state;
}

// ── Call Card + Map Pin Management ────────────────────────────────────────
function addCall(call) {
    // Remove empty state if present
    const emptyEl = document.getElementById('emptyState');
    if (emptyEl) emptyEl.remove();

    callCount++;
    callCountEl.textContent = callCount;

    const info = CALL_ICONS[call.call_type] || CALL_ICONS.other;
    const time24 = formatTime(call.timestamp);

    // ── Map marker ──────────────────────────────────────────────────────────
    const markerEl = createMarkerIcon(call.call_type);

    const leafletIcon = L.divIcon({
        html: markerEl.outerHTML,
        className: '',
        iconSize: [38, 38],
        iconAnchor: [19, 38],   // tip of the pin
        popupAnchor: [0, -38],
    });

    const marker = L.marker([call.lat, call.lng], { icon: leafletIcon, riseOnHover: true })
        .addTo(map);

    // Popup
    const popupHtml = `
    <div class="popup-card">
      <div class="popup-card__type ${call.call_type}">${info.emoji} ${info.label.toUpperCase()}</div>
      <div class="popup-card__address">${call.address}</div>
      <div class="popup-card__time">${formatTimestamp(call.timestamp)}</div>
      <div class="popup-card__desc">${call.description}</div>
    </div>
  `;
    marker.bindPopup(popupHtml, { maxWidth: 280 });

    marker.on('click', () => activateCall(call.id));

    // ── Side panel card ──────────────────────────────────────────────────────
    const card = document.createElement('div');
    card.className = `call-card ${call.call_type}`;
    card.id = `card-${call.id}`;
    card.dataset.id = call.id;
    card.innerHTML = `
    <div class="call-card__header">
      <div class="call-card__type ${call.call_type}">
        <span class="call-card__type-icon">${info.emoji}</span>
        ${info.label}
      </div>
      <div class="call-card__time">${time24}</div>
    </div>
    <div class="call-card__address">${call.address}</div>
    <div class="call-card__desc">${call.description}</div>
  `;

    card.addEventListener('click', () => activateCall(call.id));

    // Insert newest at the top
    const listEl = document.getElementById('callList');
    listEl.insertBefore(card, listEl.firstChild);

    // Grab the actual rendered marker element from the DOM for animation
    // Leaflet renders it async, so we use a small timeout
    setTimeout(() => {
        const renderedMarker = document.querySelector(`.map-marker.${call.call_type}[data-id="${call.id}"]`);
        const markerWrapper = marker.getElement();
        if (markerWrapper) markerWrapper.dataset.id = call.id;
    }, 100);

    // Register
    callRegistry.set(call.id, { marker, cardEl: card, markerEl: null });
}

// ── Activate (highlight) a call ────────────────────────────────────────────
function activateCall(callId) {
    // Deactivate previous
    if (activeCallId && callRegistry.has(activeCallId)) {
        const prev = callRegistry.get(activeCallId);
        prev.cardEl.classList.remove('active');
        const prevMarkerEl = prev.marker.getElement();
        if (prevMarkerEl) {
            const innerDiv = prevMarkerEl.querySelector('.map-marker');
            if (innerDiv) innerDiv.classList.remove('highlighted');
        }
    }

    activeCallId = callId;
    if (!callRegistry.has(callId)) return;

    const { marker, cardEl } = callRegistry.get(callId);

    // Highlight card
    cardEl.classList.add('active');
    cardEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    // Highlight marker + fly to it
    const markerEl = marker.getElement();
    if (markerEl) {
        const innerDiv = markerEl.querySelector('.map-marker');
        if (innerDiv) {
            innerDiv.classList.remove('highlighted');
            void innerDiv.offsetWidth; // re-trigger animation
            innerDiv.classList.add('highlighted');
        }
    }

    map.flyTo(marker.getLatLng(), Math.max(map.getZoom(), 13), {
        animate: true, duration: 0.8,
    });
    marker.openPopup();
}

// ── Socket.IO Connection ───────────────────────────────────────────────────
const socket = io(BACKEND_URL, { transports: ['websocket', 'polling'] });

socket.on('connect', () => {
    console.log('[Socket] Connected');
    updateStatus('connecting', 'live');
});

socket.on('disconnect', () => {
    console.log('[Socket] Disconnected');
    updateStatus('disconnected', 'live');
});

socket.on('status_update', (data) => {
    console.log('[Socket] Status:', data);
    updateStatus(data.state, data.mode);
});

socket.on('new_call', (call) => {
    console.log('[Socket] New call:', call);
    if (!callRegistry.has(call.id)) {
        addCall(call);
    }
});

// ── Load existing calls on startup ────────────────────────────────────────
fetch(`${BACKEND_URL}/api/calls`)
    .then(r => r.json())
    .then(calls => {
        // calls are newest-first; add in reverse so newest ends up on top
        [...calls].reverse().forEach(addCall);
    })
    .catch(err => console.warn('Could not load existing calls:', err));
