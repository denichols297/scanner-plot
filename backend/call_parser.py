"""
call_parser.py
Extracts address, call type, and description from raw scanner transcript text.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

FIRE_KEYWORDS = [
    'fire', 'smoke', 'flames', 'burning', 'structure fire', 'brush fire',
    'vehicle fire', 'house fire', 'barn fire', 'wildfire', 'arson', 'explosion',
]
POLICE_KEYWORDS = [
    'police', 'officer', 'assault', 'domestic', 'burglary', 'robbery', 'theft',
    'fight', 'disturbance', 'shooting', 'shots fired', 'pursuit', 'weapon',
    'suspicious', 'intruder', 'trespassing', 'missing person', 'warrant',
    'traffic stop', 'dui', 'drunk driver', 'hit and run', 'larceny', 'mvc',
]
MEDICAL_KEYWORDS = [
    'medical', 'ems', 'ambulance', 'cardiac', 'breathing', 'chest pain', 'stroke',
    'unconscious', 'unresponsive', 'overdose', 'fall', 'injury', 'trauma',
    'accident', 'crash', 'motor vehicle', 'laceration', 'seizure', 'diabetic',
    'allergic', 'anaphylaxis', 'choking', 'rescue',
]

# Patterns for addresses in upstate NY scanner traffic
_ADDR_PATTERNS = [
    # "123 Main Street" or "123 Main St"
    r'\b(\d{1,5}\s+(?:[A-Z][a-z]+\s+){1,3}(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Place|Pl|Boulevard|Blvd|Way|Circle|Cir|Highway|Hwy|Route|Rte|Rt)\.?)\b',
    # "Route 5" / "State Route 31" / "County Road 46"
    r'\b((?:State\s+)?(?:Route|County\s+Road|County\s+Rte|State\s+Route|CR|Rte?|Rt)\s+\d{1,4}[A-Z]?)\b',
    # "at Main and Oak" intersections
    r'\b(?:at|on)\s+([A-Z][a-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln))\s+(?:and|&)\s+([A-Z][a-z]+)\b',
]

_COMPILED = [(re.compile(p, re.IGNORECASE), i) for i, p in enumerate(_ADDR_PATTERNS)]


@dataclass
class Call:
    id: str
    timestamp: str          # ISO 8601
    call_type: str          # 'fire' | 'police' | 'medical' | 'other'
    address: str
    description: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    raw_transcript: str = ''

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'call_type': self.call_type,
            'address': self.address,
            'description': self.description,
            'lat': self.lat,
            'lng': self.lng,
        }


def _classify_type(text: str) -> str:
    lower = text.lower()
    fire_score = sum(1 for kw in FIRE_KEYWORDS if kw in lower)
    police_score = sum(1 for kw in POLICE_KEYWORDS if kw in lower)
    medical_score = sum(1 for kw in MEDICAL_KEYWORDS if kw in lower)
    best = max(fire_score, police_score, medical_score)
    if best == 0:
        return 'other'
    if fire_score == best:
        return 'fire'
    if medical_score == best:
        return 'medical'
    return 'police'


def _extract_address(text: str) -> Optional[str]:
    for pattern, idx in _COMPILED:
        m = pattern.search(text)
        if m:
            addr = ' '.join(g for g in m.groups() if g)
            return addr.strip()
    return None


def _clean_description(text: str) -> str:
    """First 120 chars of transcript, cleaned up."""
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > 120:
        text = text[:117] + '…'
    return text


_call_counter = 0


def parse_transcript(text: str) -> Optional[Call]:
    """Return a Call if a valid address can be extracted."""
    global _call_counter
    if not text or len(text.strip()) < 10:
        return None

    address = _extract_address(text)
    if not address:
        return None

    _call_counter += 1
    call_id = f"call_{int(datetime.now().timestamp())}_{_call_counter}"

    return Call(
        id=call_id,
        timestamp=datetime.utcnow().isoformat() + 'Z',
        call_type=_classify_type(text),
        address=address,
        description=_clean_description(text),
        raw_transcript=text,
    )
