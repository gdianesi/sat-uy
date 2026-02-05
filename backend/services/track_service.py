from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Dict, Any

from skyfield.api import wgs84, load
from tle_store import get_satellite_by_key

ts = load.timescale()
UY_TZ = ZoneInfo("America/Montevideo")

def _parse_iso_utc(dt_iso: str) -> datetime:
    dt_iso = dt_iso.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(dt_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def compute_track(
    satellite_key: str,
    start_utc: str,
    end_utc: str,
    step_seconds: int = 10,
) -> Dict[str, Any]:
    key, catnr, sat = get_satellite_by_key(satellite_key)

    start_dt = _parse_iso_utc(start_utc)
    end_dt = _parse_iso_utc(end_utc)
    if end_dt <= start_dt:
        raise ValueError("end_utc debe ser mayor que start_utc")

    # Montevideo (si tu track es global no importa, pero lo dejo consistente)
    OBS_LAT = -34.9011
    OBS_LON = -56.1645
    OBS_ALT_M = 20
    observer = wgs84.latlon(OBS_LAT, OBS_LON, elevation_m=OBS_ALT_M)

    total_seconds = int((end_dt - start_dt).total_seconds())
    n = max(2, total_seconds // step_seconds + 1)

    t0 = ts.from_datetime(start_dt)
    t1 = ts.from_datetime(end_dt)
    times = ts.linspace(t0, t1, n)

    points = []
    coords = []

    for t in times:
        dt_utc = t.utc_datetime().replace(tzinfo=timezone.utc)
        dt_uy = dt_utc.astimezone(UY_TZ)

        sp = sat.at(t).subpoint()
        lat = float(sp.latitude.degrees)
        lon = float(sp.longitude.degrees)

        points.append({
            "t_utc": dt_utc.isoformat(),
            "t_uy": dt_uy.isoformat(),
            "lat": round(lat, 6),
            "lon": round(lon, 6),
        })
        coords.append([lon, lat])  # GeoJSON: [lon, lat]

    return {
        "satellite": {"key": key, "catnr": catnr},
        "start_utc": start_dt.isoformat(),
        "end_utc": end_dt.isoformat(),
        "step_seconds": step_seconds,
        "points": points,
        "geojson": {
            "type": "Feature",
            "properties": {"key": key, "catnr": catnr},
            "geometry": {"type": "LineString", "coordinates": coords},
        }
    }
