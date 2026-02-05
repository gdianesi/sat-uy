from fastapi import APIRouter, Query, HTTPException
from typing import Optional

from services.passes_service import compute_passes_mvd
from tle_store import SATELLITES as STORE_SATELLITES  # <- unificado

router = APIRouter()

@router.get("/passes")
def passes(
    satellite: str = Query("ISS"),
    hours: int = Query(48, ge=1, le=240),
    min_elevation_deg: float = Query(10.0, ge=0.0, le=90.0),
    start_utc: Optional[str] = Query(None),
):
    if start_utc is not None and start_utc.strip() == "":
        start_utc = None

    key = satellite.strip().upper()
    if key not in STORE_SATELLITES:
        raise HTTPException(
            status_code=400,
            detail=f"Satélite inválido '{satellite}'. Opciones: {list(STORE_SATELLITES.keys())}",
        )

    try:
        return compute_passes_mvd(
            satellite_key=key,
            hours=hours,
            min_elevation_deg=min_elevation_deg,
            start_utc_iso=start_utc,  # si es None => “desde ahora” (tu modo realtime)
        )
    except ValueError as e:
        msg = str(e)
        if "No pude obtener TLE" in msg or "TLE" in msg:
            raise HTTPException(status_code=503, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
