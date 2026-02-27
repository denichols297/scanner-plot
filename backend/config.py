import os
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

BROADCASTIFY_USERNAME = os.getenv('BROADCASTIFY_USERNAME', '')
BROADCASTIFY_PASSWORD = os.getenv('BROADCASTIFY_PASSWORD', '')
BROADCASTIFY_FEED_ID  = os.getenv('BROADCASTIFY_FEED_ID', '29700')
WHISPER_MODEL         = os.getenv('WHISPER_MODEL', 'base.en')

# Demo mode: on if no credentials, or env flag is set
_demo_env = os.getenv('DEMO_MODE', 'false').lower()
DEMO_MODE = (_demo_env == 'true') or not (BROADCASTIFY_USERNAME and BROADCASTIFY_PASSWORD)

STREAM_URL = (
    f"https://{BROADCASTIFY_USERNAME}:{BROADCASTIFY_PASSWORD}"
    f"@audio.broadcastify.com/{BROADCASTIFY_FEED_ID}.mp3"
)

# Oneida County, NY centroid – fallback geocode
COUNTY_LAT = 43.235
COUNTY_LNG = -75.398
