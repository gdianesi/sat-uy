from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from zoneinfo import ZoneInfo

from skyfield.api import load, wgs84

from tle_store import get_satellite_by_key

ts = load.timescale()
UY_TZ = ZoneInfo("America/Montevideo")

def compute_track_now(
    satellite_key: str,
    minutes: int = 20,
    step_seconds: int = 10,
) -> Dict[str, Any]:
    if minutes < 1 or minutes > 180:
        raise ValueError("minutes debe estar entre 1 y 180")
    if step_seconds < 1 or step_seconds > 120:
        raise ValueError("step_seconds debe estar entre 1 y 120")

    key, catnr, sat = get_satellite_by_key(satellite_key, allow_network=True)

    start_dt = datetime.now(timezone.utc)
    end_dt = start_dt + timedelta(minutes=minutes)

    # Generamos instantes
    times_dt: List[datetime] = []
    t = start_dt
    while t <= end_dt:
        times_dt.append(t)
        t += timedelta(seconds=step_seconds)

    t_sf = ts.from_datetimes(times_dt)

    geoc = sat.at(t_sf)
    subs = wgs84.subpoint(geoc)

    points = []
    for dt, lat, lon in zip(times_dt, subs.latitude.degrees, subs.longitude.degrees):
        dt_uy = dt.astimezone(UY_TZ)
        points.append({
            "t_utc": dt.isoformat(),
            "t_uy": dt_uy.isoformat(),
            "lat": round(float(lat), 6),
            "lon": round(float(lon), 6),
        })

    geojson = {
        "type": "Feature",
        "properties": {"key": key, "catnr": catnr},
        "geometry": {
            "type": "LineString",
            "coordinates": [[p["lon"], p["lat"]] for p in points],
        },
    }

    return {
        "satellite": {"key": key, "catnr": catnr},
        "minutes": minutes,
        "step_seconds": step_seconds,
        "start_utc": start_dt.isoformat(),
        "end_utc": end_dt.isoformat(),
        "points": points,
        "geojson": geojson,
    }
