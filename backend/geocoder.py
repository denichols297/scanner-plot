"""
geocoder.py
Geocodes extracted addresses to lat/lng using Nominatim (OpenStreetMap, free).
Constrains search to Oneida/Herkimer/Madison counties, NY.
Caches results to respect rate limiting.
"""
import time
import logging
from typing import Optional, Tuple
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from config import COUNTY_LAT, COUNTY_LNG

log = logging.getLogger(__name__)

_geolocator = Nominatim(
    user_agent='scanner-plot/1.0 (Oneida County NY Public Safety)',
    timeout=5,
)

# Known county fallback centroids
COUNTY_CENTROIDS = {
    'oneida':   (43.235, -75.398),
    'herkimer': (43.092, -74.978),
    'madison':  (42.930, -75.678),
}

_cache: dict[str, Tuple[float, float]] = {}

# Bounding box for the three-county area (roughly)
_COUNTY_AREA = 'Oneida County, New York, USA'


def geocode_address(address: str) -> Tuple[float, float]:
    """Return (lat, lng) for address, or county centroid on failure."""
    if address in _cache:
        return _cache[address]

    queries = [
        f"{address}, {_COUNTY_AREA}",
        f"{address}, New York, USA",
    ]

    for query in queries:
        try:
            time.sleep(1.1)  # Nominatim rate limit: max 1 req/sec
            location = _geolocator.geocode(query)
            if location:
                result = (location.latitude, location.longitude)
                _cache[address] = result
                log.info(f"Geocoded '{address}' → {result}")
                return result
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            log.warning(f"Geocoder error for '{query}': {e}")

    log.warning(f"Could not geocode '{address}', using county centroid")
    # Jitter the centroid slightly so stacked pins are visible
    import random
    jitter_lat = COUNTY_LAT + random.uniform(-0.02, 0.02)
    jitter_lng = COUNTY_LNG + random.uniform(-0.03, 0.03)
    result = (jitter_lat, jitter_lng)
    _cache[address] = result
    return result
