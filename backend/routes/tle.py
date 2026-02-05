from fastapi import APIRouter, Query, HTTPException

from tle_store import SATELLITES
from tle_store import refresh_tle_or_raise
from tle_store import _meta_path

import json

router = APIRouter(prefix="/tle", tags=["tle"])

@router.post("/refresh")
def refresh_tle(satellite: str = Query("ISS")):
    key = satellite.strip().upper()
    if key not in SATELLITES:
        raise HTTPException(
            status_code=400,
            detail=f"Satélite inválido '{satellite}'. Opciones: {list(SATELLITES.keys())}",
        )

    catnr = SATELLITES[key]
    try:
        refresh_tle_or_raise(catnr)
        return {"satellite": {"key": key, "catnr": catnr}, "refreshed": True}
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/meta")
def tle_meta(satellite: str = Query("ISS")):
    key = satellite.strip().upper()
    if key not in SATELLITES:
        raise HTTPException(
            status_code=400,
            detail=f"Satélite inválido '{satellite}'. Opciones: {list(SATELLITES.keys())}",
        )

    catnr = SATELLITES[key]
    p = _meta_path(catnr)
    if not p.exists():
        return {"satellite": {"key": key, "catnr": catnr}, "meta": None}

    try:
        meta = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        meta = None

    return {"satellite": {"key": key, "catnr": catnr}, "meta": meta}

from tle_store import SATELLITES, refresh_tle_best_effort

@router.post("/refresh-all")
def refresh_all():
    results = []
    for key, catnr in SATELLITES.items():
        ok = refresh_tle_best_effort(catnr)
        results.append({"key": key, "catnr": catnr, "refreshed": ok})
    return {"results": results}
