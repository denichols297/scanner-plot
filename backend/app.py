"""
app.py
Flask + Flask-SocketIO server for the scanner-plot web app.
Orchestrates the stream listener, transcriber, parser, and geocoder pipelines.
Serves the frontend and pushes real-time events via WebSocket.
"""
import logging
import queue
import sys
import threading
from pathlib import Path


from flask import Flask, jsonify, send_from_directory
from flask_socketio import SocketIO
from flask_cors import CORS

from config import DEMO_MODE, WHISPER_MODEL
from stream_listener import StreamListener
import call_parser
import geocoder

# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger('app')

# ---------------------------------------------------------------------------
FRONTEND_DIR = Path(__file__).parent.parent / 'frontend'

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path='')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

# ---------------------------------------------------------------------------
# In-memory call store
# ---------------------------------------------------------------------------
all_calls: list[dict] = []
calls_lock = threading.Lock()

# Inter-thread queue for the pipeline
event_queue: queue.Queue = queue.Queue()

# Current stream status
stream_status = {'state': 'connecting', 'mode': 'demo' if DEMO_MODE else 'live'}


# ---------------------------------------------------------------------------
# Pipeline thread: processes events from the queue
# ---------------------------------------------------------------------------
def pipeline_worker():
    """Reads events from event_queue and processes them."""
    if not DEMO_MODE:
        # Only import transcriber in live mode (loads Whisper model)
        import transcriber

    while True:
        try:
            event_type, payload = event_queue.get(timeout=1)
        except queue.Empty:
            continue

        if event_type == 'status':
            stream_status['state'] = payload
            socketio.emit('status_update', {
                'state': payload,
                'mode': stream_status['mode'],
            })
            log.info(f"Stream status: {payload}")

        elif event_type == 'transcript':
            # Demo mode sends transcripts directly
            _process_transcript(payload)

        elif event_type == 'audio':
            # Live mode sends raw PCM bytes
            try:
                transcript = transcriber.transcribe_chunk(payload)
                if transcript:
                    _process_transcript(transcript)
            except Exception as e:
                log.error(f"Transcription error: {e}")


def _process_transcript(text: str):
    """Parse → geocode → store → emit."""
    log.info(f"Processing transcript: {text[:80]}…")
    call = call_parser.parse_transcript(text)
    if not call:
        log.debug("No address found in transcript, skipping.")
        return

    # Geocode (may block ~1 sec for Nominatim rate limit)
    try:
        lat, lng = geocoder.geocode_address(call.address)
        call.lat = lat
        call.lng = lng
    except Exception as e:
        log.error(f"Geocode error: {e}")
        from config import COUNTY_LAT, COUNTY_LNG
        call.lat, call.lng = COUNTY_LAT, COUNTY_LNG

    call_dict = call.to_dict()

    with calls_lock:
        all_calls.insert(0, call_dict)          # newest first
        if len(all_calls) > 500:                # cap memory usage
            all_calls.pop()

    log.info(f"New call: [{call.call_type.upper()}] {call.address} @ ({call.lat:.4f}, {call.lng:.4f})")
    socketio.emit('new_call', call_dict)


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------
@app.route('/api/calls')
def get_calls():
    with calls_lock:
        return jsonify(all_calls)


@app.route('/api/status')
def get_status():
    return jsonify(stream_status)


# ---------------------------------------------------------------------------
# Frontend serving
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return send_from_directory(str(FRONTEND_DIR), 'index.html')


@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(str(FRONTEND_DIR), filename)


# ---------------------------------------------------------------------------
# SocketIO events
# ---------------------------------------------------------------------------
@socketio.on('connect')
def on_connect():
    log.info('Client connected')
    socketio.emit('status_update', stream_status)
    with calls_lock:
        # Send all existing calls to newly connected client
        for call in all_calls:
            socketio.emit('new_call', call)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
def start_background_threads():
    mode_str = "DEMO" if DEMO_MODE else "LIVE"
    log.info(f"Starting scanner-plot backend [{mode_str} mode]")

    # Pipeline worker thread
    pipeline_thread = threading.Thread(target=pipeline_worker, daemon=True)
    pipeline_thread.start()

    # Stream listener
    listener = StreamListener(event_queue)
    listener.start()

    if DEMO_MODE:
        stream_status['state'] = 'demo'
        log.info("Demo mode: simulated calls will appear every 12–25 seconds.")
    else:
        stream_status['state'] = 'connecting'


if __name__ == '__main__':
    start_background_threads()
    port = 5050
    log.info(f"Scanner-Plot running at http://localhost:{port}")
    log.info(f"Press Ctrl+C to stop.")
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
