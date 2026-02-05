from fastapi import APIRouter, Query, HTTPException

from tle_store import SATELLITES, TLE_TTL
from tle_store import (
    read_meta_public,
    tle_file_exists,
    tle_file_mtime_utc,
    tle_age_seconds,
    is_stale,
)

router = APIRouter(prefix="/tle", tags=["tle"])

@router.get("/status")
def tle_status(satellite: str = Query(None)):
    def one(key: str):
        catnr = SATELLITES[key]
        meta = read_meta_public(catnr)
        age = tle_age_seconds(catnr)

        return {
            "key": key,
            "catnr": catnr,
            "has_local": tle_file_exists(catnr),
            "mtime_utc": tle_file_mtime_utc(catnr),
            "meta": meta,
            "age_seconds": age,
            "age_minutes": None if age is None else round(age / 60, 2),
            "ttl_seconds": int(TLE_TTL.total_seconds()),
            "stale": is_stale(catnr),
        }

    # si no mandan satellite -> status de todos
    if satellite is None:
        return {"satellites": [one(k) for k in SATELLITES.keys()]}

    key = satellite.strip().upper()
    if key not in SATELLITES:
        raise HTTPException(
            status_code=400,
            detail=f"Satélite inválido '{satellite}'. Opciones: {list(SATELLITES.keys())}",
        )

    return one(key)
