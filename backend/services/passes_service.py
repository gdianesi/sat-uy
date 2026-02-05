from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any

from skyfield.api import wgs84, load
from tle_store import get_satellite_by_key

ts = load.timescale()
UY_TZ = ZoneInfo("America/Montevideo")

OBS_LAT = -34.9011
OBS_LON = -56.1645
OBS_ALT_M = 20

def _parse_iso_utc(dt_iso: str) -> datetime:
    dt_iso = dt_iso.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(dt_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def compute_passes_mvd(
    satellite_key: str,
    hours: int = 24,
    min_elevation_deg: float = 10.0,
    start_utc_iso: Optional[str] = None,
) -> Dict[str, Any]:

    if start_utc_iso is not None and start_utc_iso.strip() == "":
        start_utc_iso = None

    key, catnr, satellite = get_satellite_by_key(satellite_key, allow_network=True)

    observer = wgs84.latlon(OBS_LAT, OBS_LON, elevation_m=OBS_ALT_M)

    start_dt = _parse_iso_utc(start_utc_iso) if start_utc_iso else datetime.now(timezone.utc)
    end_dt = start_dt + timedelta(hours=hours)

    t0 = ts.from_datetime(start_dt)
    t1 = ts.from_datetime(end_dt)

    times, events = satellite.find_events(observer, t0, t1, altitude_degrees=min_elevation_deg)

    results = []
    current = {}

    for t, e in zip(times, events):
        dt_utc = t.utc_datetime().replace(tzinfo=timezone.utc)
        dt_uy = dt_utc.astimezone(UY_TZ)

        if e == 0:
            current = {"rise_utc": dt_utc.isoformat(), "rise_uy": dt_uy.isoformat()}
        elif e == 1:
            topocentric = (satellite - observer).at(t)
            alt, az, dist = topocentric.altaz()
            current.update({
                "culmination_utc": dt_utc.isoformat(),
                "culmination_uy": dt_uy.isoformat(),
                "max_elevation_deg": round(float(alt.degrees), 2),
            })
        elif e == 2:
            current.update({"set_utc": dt_utc.isoformat(), "set_uy": dt_uy.isoformat()})
            if "max_elevation_deg" in current:
                results.append(current)
            current = {}

    return {
        "satellite": {"key": key, "catnr": catnr},
        "observer": {"lat": OBS_LAT, "lon": OBS_LON, "alt_m": OBS_ALT_M},
        "hours": hours,
        "min_elevation_deg": min_elevation_deg,
        "start_utc": start_dt.isoformat(),
        "end_utc": end_dt.isoformat(),
        "passes": results,
    }
