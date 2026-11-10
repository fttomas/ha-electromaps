"""Constants for the Electromaps integration."""

from typing import Final

DOMAIN: Final = "electromaps"

API_URL: Final = "https://www.electromaps.com/mapi/v2/locations/{location_id}"
MAP_URL: Final = "https://map.electromaps.com/en/p/{location_id}"

CONF_LOCATION_ID: Final = "location_id"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 30
MAX_SCAN_INTERVAL: Final = 3600
# Ceiling for the pause after repeated failures, so a broken API is not hammered.
MAX_BACKOFF: Final = 900
REQUEST_TIMEOUT: Final = 10

STATUS_AVAILABLE: Final = "available"
STATUS_OCCUPIED: Final = "occupied"
STATUS_OUT_OF_SERVICE: Final = "out_of_service"
STATUS_UNKNOWN: Final = "unknown"
STATUSES: Final = [
    STATUS_AVAILABLE,
    STATUS_OCCUPIED,
    STATUS_OUT_OF_SERVICE,
    STATUS_UNKNOWN,
]
