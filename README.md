# 📡 Scanner Plot

Real-time emergency call map for **Oneida, Herkimer, and Madison Counties, NY**.

Listens to the Broadcastify public safety scanner feed, transcribes audio with Whisper, extracts addresses and call types, geocodes them, and plots them live on an interactive dark map.

---

## Quick Start

```bash
cd scanner-plot
bash run.sh
```

Then open **http://localhost:5050** in your browser.

---

## Live Mode (Broadcastify Premium)

1. Copy `.env.example` to `.env`
2. Fill in your Broadcastify credentials:
   ```
   BROADCASTIFY_USERNAME=your_username
   BROADCASTIFY_PASSWORD=your_password
   BROADCASTIFY_FEED_ID=29700
   ```
3. Install ffmpeg if you haven't:
   ```bash
   brew install ffmpeg
   ```
4. Run `bash run.sh`

## Demo Mode (default)

If you don't have Broadcastify credentials, leave `.env` blank — the app automatically runs in **Demo Mode**, injecting 20 realistic scanner call transcripts every 12–25 seconds to demonstrate all features.

---

## Features

- 🗺️ **Live Leaflet map** centered on Oneida County, NY (dark CartoDB tile layer)
- 🔥 Fire / 🚔 Police / 🚑 Medical / ⚠️ Other — custom color-coded map pins
- 📋 **Side panel** listing calls newest-first with type, address, time, description
- 🖱️ **Click any call** → map flies to it and the pin pulses
- 📡 **Status bar** shows stream state + live 24h clock
- 🤖 **local faster-whisper** transcription (no OpenAI key required)
- 🆓 **Nominatim** geocoding (OpenStreetMap, free, no key required)

---

## Architecture

```
Broadcastify MP3 stream
        ↓
stream_listener.py (ffmpeg → 16kHz PCM chunks)
        ↓
transcriber.py (faster-whisper)
        ↓
call_parser.py (regex + keyword extraction)
        ↓
geocoder.py (Nominatim)
        ↓
app.py (Flask-SocketIO → WebSocket)
        ↓
frontend/app.js (Leaflet.js + Socket.IO)
```

---

## Whisper Models

Set `WHISPER_MODEL` in `.env`:

| Model      | Size   | Speed | Accuracy |
|------------|--------|-------|----------|
| `tiny.en`  | ~75 MB | ⚡⚡⚡ | ★★☆     |
| `base.en`  | ~140 MB| ⚡⚡   | ★★★  ← default |
| `small.en` | ~460 MB| ⚡     | ★★★★    |
| `medium.en`| ~1.5 GB| 🐢    | ★★★★★   |
