from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Any

from skyfield.api import wgs84, load

from tle_store import get_satellite_by_key

ts = load.timescale()
UY_TZ = ZoneInfo("America/Montevideo")


def compute_position_now(satellite_key: str) -> Dict[str, Any]:
    key, catnr, sat = get_satellite_by_key(satellite_key, allow_network=True)

    t = ts.now()
    dt_utc = t.utc_datetime().replace(tzinfo=timezone.utc)
    dt_uy = dt_utc.astimezone(UY_TZ)

    geocentric = sat.at(t)
    sub = wgs84.subpoint(geocentric)

    lat = float(sub.latitude.degrees)
    lon = float(sub.longitude.degrees)
    alt_km = float(sub.elevation.km)

    return {
        "satellite": {"key": key, "catnr": catnr},
        "t_utc": dt_utc.isoformat(),
        "t_uy": dt_uy.isoformat(),
        "position": {
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "alt_km": round(alt_km, 3),
        },
    }
