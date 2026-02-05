from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from services.position_service import compute_position_now
from routes.passes import router as passes_router
from routes.track import router as track_router
from routes.satellites import router as satellites_router
from services.track_now_service import compute_track_now
from routes.tle import router as tle_router
from routes.status import router as status_router
import os
from tle_store import SATELLITES, refresh_tle_best_effort, is_stale

app = FastAPI(title="sat-uy (offline-first)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "utc": datetime.now(timezone.utc).isoformat()}

@app.get("/position")
def position(
    satellite: str = Query("ISS"),
):
    try:
        return compute_position_now(satellite)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/track/now")
def track_now(
    satellite: str = Query("ISS"),
    minutes: int = Query(20, ge=1, le=180),
    step_seconds: int = Query(10, ge=1, le=120),
):
    try:
        return compute_track_now(
            satellite_key=satellite,
            minutes=minutes,
            step_seconds=step_seconds,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.on_event("startup")
def _startup_refresh_tles():
    # Permite desactivar en dev/CI si querés:
    if os.getenv("DISABLE_TLE_REFRESH", "0") == "1":
        return

    for key, catnr in SATELLITES.items():
        try:
            if is_stale(catnr):
                ok = refresh_tle_best_effort(catnr)
                print(f"[TLE] startup refresh {key} ({catnr}) -> {ok}")
            else:
                print(f"[TLE] startup skip {key} ({catnr}) fresh")
        except Exception as e:
            print(f"[TLE] startup refresh error {key} ({catnr}): {e}")

app.include_router(passes_router)
app.include_router(track_router)
app.include_router(satellites_router)
app.include_router(tle_router)
app.include_router(status_router)


