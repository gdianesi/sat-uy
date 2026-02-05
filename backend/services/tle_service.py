# backend/services/tle_service.py
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Tuple

import httpx

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DEBUG_TLE = True

print("DEBUG DATA_DIR =", DATA_DIR)
print("DEBUG exists DATA_DIR =", DATA_DIR.exists())
print("DEBUG files =", list(DATA_DIR.glob("*"))[:10])

# Cache en memoria: {catnr: (fetched_at_utc, name, line1, line2)}
_CACHE: Dict[int, Tuple[datetime, str, str, str]] = {}
_CACHE_TTL = timedelta(hours=6)

# Ponelo en True SOLO para debug y luego volvelo a False
DEBUG_TLE = False


def _read_local_tle(catnr: int) -> tuple[str, str, str] | None:
    p = DATA_DIR / f"tle_{catnr}.txt"
    if not p.exists():
        return None

    lines = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(lines) < 3:
        return None

    name, line1, line2 = lines[0], lines[1], lines[2]
    try:
        only_catnr = int(line1.split()[1])
    except Exception:
        return None

    if only_catnr != catnr or not line1.startswith("1 ") or not line2.startswith("2 "):
        return None

    return name, line1, line2


def _save_local_tle(catnr: int, name: str, line1: str, line2: str) -> None:
    p = DATA_DIR / f"tle_{catnr}.txt"
    p.write_text(f"{name}\n{line1}\n{line2}\n", encoding="utf-8")


def _cache_get(catnr: int) -> tuple[str, str, str] | None:
    item = _CACHE.get(catnr)
    if not item:
        return None

    fetched_at, name, line1, line2 = item
    if datetime.now(timezone.utc) - fetched_at > _CACHE_TTL:
        return None

    return name, line1, line2


def _cache_set(catnr: int, name: str, line1: str, line2: str) -> None:
    _CACHE[catnr] = (datetime.now(timezone.utc), name, line1, line2)


def _parse_tle_text_any(text: str, catnr: int) -> tuple[str, str, str] | None:
    """
    Parser robusto:
    busca una línea "1 <catnr>" y toma la siguiente como "2 ...",
    y la anterior como nombre.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    for i in range(1, len(lines) - 1):
        line1 = lines[i]
        if not line1.startswith("1 "):
            continue

        try:
            found_catnr = int(line1.split()[1])
        except Exception:
            continue

        if found_catnr != catnr:
            continue

        line2 = lines[i + 1]
        if not line2.startswith("2 "):
            continue

        name = lines[i - 1] if i - 1 >= 0 else f"CATNR {catnr}"
        return name, line1, line2

    return None


def _fetch_tle_from_tleapi(catnr: int) -> tuple[str, str, str] | None:
    """
    Fuente alternativa (JSON):
    https://tle.ivanstanojevic.me/api/tle/{catnr}
    """
    url = f"https://tle.ivanstanojevic.me/api/tle/{catnr}"
    try:
        r = httpx.get(url, timeout=10.0)
        r.raise_for_status()
        j = r.json()
        name = j.get("name") or f"CATNR {catnr}"
        line1 = j.get("line1")
        line2 = j.get("line2")
        if not line1 or not line2:
            return None
        if not line1.startswith("1 ") or not line2.startswith("2 "):
            return None
        return name, line1, line2
    except Exception:
        return None


def fetch_tle_from_celestrak(catnr: int) -> tuple[str, str, str]:
    cached = _cache_get(catnr)
    if cached:
        return cached

    # ✅ fallback local primero
    local = _read_local_tle(catnr)
    if local:
        name, line1, line2 = local
        _cache_set(catnr, name, line1, line2)
        return name, line1, line2

    # (si querés, después intentás fuentes externas para refrescar)
    alt = _fetch_tle_from_tleapi(catnr)
    if alt:
        name, line1, line2 = alt
        _cache_set(catnr, name, line1, line2)
        _save_local_tle(catnr, name, line1, line2)
        return name, line1, line2

    headers = {
        "User-Agent": "sat-uy/0.1 (FastAPI; contact: local-dev)",
        "Accept": "text/plain,*/*",
    }

    urls = [
        f"https://celestrak.org/NORAD/elements/gp.php?CATNR={catnr}&FORMAT=TLE",
        f"https://celestrak.com/NORAD/elements/gp.php?CATNR={catnr}&FORMAT=TLE",
    ]

    last_err: Exception | None = None

    with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
        for url in urls:
            try:
                resp = client.get(url)
                if resp.status_code == 403:
                    last_err = httpx.HTTPStatusError(
                        f"403 Forbidden for {url}", request=resp.request, response=resp
                    )
                    continue

                resp.raise_for_status()

                parsed = _parse_tle_text_any(resp.text, catnr)
                if parsed:
                    name, line1, line2 = parsed
                    _cache_set(catnr, name, line1, line2)
                    _save_local_tle(catnr, name, line1, line2)
                    return name, line1, line2

                last_err = ValueError(
                    f"Respuesta no-TLE desde {url} (status={resp.status_code}, content-type={resp.headers.get('content-type')})"
                )

            except Exception as e:
                last_err = e
                continue

    raise ValueError(f"No pude obtener TLE para CATNR={catnr}. Último error: {last_err}")

