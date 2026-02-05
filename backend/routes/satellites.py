from fastapi import APIRouter
from tle_store import list_satellites, read_meta_public, tle_file_exists, tle_file_mtime_utc, tle_age_seconds, is_stale

router = APIRouter()

@router.get("/satellites")
def satellites():
    sats = []
    for s in list_satellites():
        catnr = s["catnr"]
        meta = read_meta_public(catnr) or {}
        sats.append({
            **s,
            "has_tle_local": tle_file_exists(catnr),
            "tle_mtime_utc": tle_file_mtime_utc(catnr),
            "tle_age_seconds": tle_age_seconds(catnr),
            "stale": is_stale(catnr),
            "source": meta.get("source"),
            "fetched_at_utc": meta.get("fetched_at_utc"),
        })
    return {"satellites": sats}
