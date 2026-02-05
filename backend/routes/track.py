from fastapi import APIRouter, Query, HTTPException
from services.track_service import compute_track

router = APIRouter()

@router.get("/track")
def track(
    satellite: str = Query("ISS"),
    start_utc: str = Query(...),
    end_utc: str = Query(...),
    step_seconds: int = Query(10, ge=1, le=120),
):
    try:
        return compute_track(
            satellite_key=satellite,
            start_utc=start_utc,
            end_utc=end_utc,
            step_seconds=step_seconds,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
