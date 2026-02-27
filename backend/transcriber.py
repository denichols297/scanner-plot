"""
transcriber.py
Wraps faster-whisper for chunked audio transcription.
Accepts raw 16kHz mono PCM bytes, returns text strings.
"""
import logging
import queue
import threading
import numpy as np
from faster_whisper import WhisperModel
from config import WHISPER_MODEL

log = logging.getLogger(__name__)

_model: WhisperModel | None = None
_model_lock = threading.Lock()


def _load_model():
    global _model
    if _model is None:
        log.info(f"Loading faster-whisper model '{WHISPER_MODEL}' (first run may download ~140 MB)…")
        _model = WhisperModel(WHISPER_MODEL, device='cpu', compute_type='int8')
        log.info("Whisper model loaded.")
    return _model


def transcribe_chunk(pcm_bytes: bytes, sample_rate: int = 16000) -> str:
    """
    Transcribe a chunk of raw 16-bit mono PCM audio.
    Returns the transcript string (may be empty for silence).
    """
    model = _load_model()
    if len(pcm_bytes) < 3200:  # < 0.1 sec at 16kHz 16-bit
        return ''

    # Convert bytes → float32 numpy array in range [-1, 1]
    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    segments, _ = model.transcribe(
        audio,
        language='en',
        vad_filter=True,          # Skip silence automatically
        vad_parameters={'min_silence_duration_ms': 500},
    )

    transcript = ' '.join(seg.text.strip() for seg in segments)
    if transcript:
        log.debug(f"Transcript: {transcript}")
    return transcript.strip()
