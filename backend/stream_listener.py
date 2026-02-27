"""
stream_listener.py
Connects to the Broadcastify MP3 stream and yields 5-second PCM audio chunks.
Falls back to Demo Mode when no credentials are configured.
"""
import io
import logging
import queue
import subprocess
import threading
import time
import random
from datetime import datetime

import requests

from config import DEMO_MODE, STREAM_URL

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Demo-mode transcripts – realistic upstate NY scanner traffic
# ---------------------------------------------------------------------------
_DEMO_TRANSCRIPTS = [
    "Engine 1, Engine 3, Ladder 2 respond to a structure fire, 247 Genesee Street, Utica, NY, for a reported house fire with people trapped",
    "Unit 14 respond to 836 Bleecker Street Utica for a domestic disturbance, caller reports male party refusing to leave the premises",
    "Oneida County EMS, respond to 1102 Kemble Street New Hartford for a 68-year-old male with chest pain and shortness of breath",
    "Engine 46, Tanker 46 respond to a brush fire on Route 12 near County Road 89 in Westmoreland",
    "All units be advised, shots fired reported at 318 Columbia Street Rome, multiple callers confirming",
    "Medic 5, respond to 204 Park Avenue Utica, unconscious non-responsive female, unknown age",
    "Squad 2, Ladder 1 respond to a reported vehicle fire on the Thruway westbound near exit 31 Rome",
    "Hamilton Police, respond to 14 Milford Street Hamilton for an alarm activation, possible burglary in progress",
    "Herkimer County EMS, respond to 4 North Main Street Herkimer for a fall victim, elderly male, possible hip fracture",
    "Oneida Unit 7 respond to 5502 Commercial Drive New Hartford for a report of an intoxicated driver, silver pickup heading northbound",
    "Rome Fire Department, Engine 12, respond to 126 West Thomas Street Rome for smoke coming from the basement",
    "Engine 38, respond to County Road 46 in Kirkland for a motor vehicle accident with injuries, vehicle into a tree",
    "Madison County Sheriff, respond to 7821 State Route 20 Madison for a disturbance, neighbor dispute with weapons mentioned",
    "Cazenovia ambulance, respond to 59 Sullivan Street Cazenovia, 45-year-old male with a seizure, currently post-ictal",
    "Oneida City Police, all units respond to the area of 112 Main Street Oneida for a fight in progress, multiple subjects involved",
    "Herkimer Fire, Engine 51, respond to 301 North Washington Street Herkimer for an oven fire, smoke showing from second floor windows",
    "EMS respond to 2211 Oneida Street Utica for a 32-year-old female, possible overdose, patient unresponsive",
    "Troop D, respond to State Route 5 westbound near the Canastota exit for a three-car motor vehicle accident, injuries reported",
    "Ladder 4, Engine 7 respond to 1400 Burstone Road New Hartford for an electrical fire, sparks and smoke from the panel",
    "Warsaw Unit 12 respond to 87 Canal Street Waterville for a report of a suspicious male looking into vehicle windows",
]


class StreamListener:
    """
    Emits PCM audio chunks (16kHz mono 16-bit) for the transcriber.
    In demo mode, emits fake transcript strings instead.
    """

    def __init__(self, transcript_queue: queue.Queue):
        self._q = transcript_queue
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self):
        self._running = True
        if DEMO_MODE:
            log.info("Demo Mode active – injecting simulated scanner calls.")
            self._thread = threading.Thread(target=self._demo_loop, daemon=True)
        else:
            log.info(f"Connecting to Broadcastify stream…")
            self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    # ------------------------------------------------------------------
    # Demo mode: put pre-canned transcripts directly into the queue
    # ------------------------------------------------------------------
    def _demo_loop(self):
        time.sleep(3)  # Brief startup pause
        idx = 0
        while self._running:
            transcript = _DEMO_TRANSCRIPTS[idx % len(_DEMO_TRANSCRIPTS)]
            log.info(f"[DEMO] Injecting transcript: {transcript}")
            self._q.put(('transcript', transcript))
            idx += 1
            # Random delay 12–25 seconds between calls
            time.sleep(random.uniform(12, 25))

    # ------------------------------------------------------------------
    # Live mode: stream MP3 → ffmpeg → PCM chunks → queue
    # ------------------------------------------------------------------
    def _stream_loop(self):
        while self._running:
            try:
                self._connect_and_stream()
            except Exception as e:
                log.error(f"Stream error: {e}. Reconnecting in 10s…")
                self._q.put(('status', 'error'))
                time.sleep(10)

    def _connect_and_stream(self):
        CHUNK_DURATION_SEC = 5
        SAMPLE_RATE = 16000
        CHANNELS = 1
        BYTES_PER_SAMPLE = 2  # 16-bit
        CHUNK_BYTES = CHUNK_DURATION_SEC * SAMPLE_RATE * CHANNELS * BYTES_PER_SAMPLE

        # ffmpeg: decode MP3 stream → raw PCM 16kHz mono s16le
        ffmpeg_cmd = [
            'ffmpeg', '-loglevel', 'error',
            '-i', 'pipe:0',
            '-ar', str(SAMPLE_RATE),
            '-ac', str(CHANNELS),
            '-f', 's16le',
            'pipe:1',
        ]

        session = requests.Session()
        session.headers['User-Agent'] = 'Mozilla/5.0'

        log.info(f"Opening HTTP stream: {STREAM_URL.replace(':'.join(STREAM_URL.split(':')[1:2]), ':***')}")
        resp = session.get(STREAM_URL, stream=True, timeout=30)
        resp.raise_for_status()
        self._q.put(('status', 'connected'))
        log.info("Stream connected.")

        proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        def feed_ffmpeg():
            try:
                for chunk in resp.iter_content(chunk_size=4096):
                    if not self._running:
                        break
                    proc.stdin.write(chunk)
                proc.stdin.close()
            except Exception as e:
                log.warning(f"Feed thread error: {e}")
                proc.stdin.close()

        feeder = threading.Thread(target=feed_ffmpeg, daemon=True)
        feeder.start()

        buf = b''
        try:
            while self._running:
                data = proc.stdout.read(4096)
                if not data:
                    break
                buf += data
                while len(buf) >= CHUNK_BYTES:
                    pcm_chunk = buf[:CHUNK_BYTES]
                    buf = buf[CHUNK_BYTES:]
                    self._q.put(('audio', pcm_chunk))
        finally:
            proc.terminate()
            resp.close()
            self._q.put(('status', 'disconnected'))
