from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Tuple, Optional

import httpx
from skyfield.api import EarthSatellite, load

ts = load.timescale()

# Carpeta: backend/data
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Cada cuánto intentamos refrescar TLE (si hay internet)
TLE_TTL = timedelta(hours=6)

# Evitar martillar fuentes externas si el frontend hace polling
_LAST_REFRESH_ATTEMPT: Dict[int, datetime] = {}
_REFRESH_COOLDOWN = timedelta(minutes=2)

# Satélites disponibles (key -> NORAD CATNR)
SATELLITES: Dict[str, int] = {
    "ISS": 25544,
    "HST": 20580,
    "NOAA-20": 43013,
    "SENTINEL-2A": 40697,
    "NOAA-15": 25338,
    "NOAA-19": 33591,
    "METEOR-M2": 40069,
    "SENTINEL-1A": 39634,
    "SUOMI-NPP": 37849,
}


@dataclass(frozen=True)
class TLE:
    name: str
    line1: str
    line2: str


def list_satellites() -> list[dict]:
    return [{"key": k, "catnr": v} for k, v in SATELLITES.items()]


def _tle_path(catnr: int) -> Path:
    return DATA_DIR / f"tle_{catnr}.txt"


def _meta_path(catnr: int) -> Path:
    return DATA_DIR / f"tle_{catnr}.meta.json"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _read_meta(catnr: int) -> Optional[dict]:
    p = _meta_path(catnr)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_meta(catnr: int, source: str) -> None:
    p = _meta_path(catnr)
    meta = {
        "catnr": catnr,
        "fetched_at_utc": _now_utc().isoformat(),
        "source": source,
    }
    p.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _parse_catnr_from_line1(line1: str) -> int:
    # En TLE real: line1.split()[1] es "25544U"
    token = line1.split()[1]
    digits = "".join(ch for ch in token if ch.isdigit())
    if not digits:
        raise ValueError("no pude leer CATNR en line1")
    return int(digits)


def _read_tle_file(path: Path, catnr: int) -> TLE:
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(lines) < 3:
        raise ValueError(f"TLE inválido: {path.name} (esperaba 3 líneas)")

    name, line1, line2 = lines[0], lines[1], lines[2]

    # por si hay BOM invisible
    line1 = line1.lstrip("\ufeff")

    if not line1.startswith("1 ") or not line2.startswith("2 "):
        raise ValueError(f"TLE inválido: {path.name} (líneas 1/2 no empiezan con '1 ' y '2 ')")

    found = _parse_catnr_from_line1(line1)
    if found != catnr:
        raise ValueError(f"TLE inválido: {path.name} (CATNR {found} != {catnr})")

    return TLE(name=name, line1=line1, line2=line2)


def _atomic_write_tle(catnr: int, name: str, line1: str, line2: str) -> None:
    path = _tle_path(catnr)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(f"{name}\n{line1}\n{line2}\n", encoding="utf-8")
    tmp.replace(path)


def _needs_refresh(catnr: int) -> bool:
    meta = _read_meta(catnr)
    if not meta:
        # si no hay meta, usamos mtime del archivo si existe
        p = _tle_path(catnr)
        if not p.exists():
            return True
        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        return (_now_utc() - mtime) > TLE_TTL

    try:
        fetched = datetime.fromisoformat(meta["fetched_at_utc"])
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        return (_now_utc() - fetched) > TLE_TTL
    except Exception:
        return True


def _fetch_tle_from_satnogs(catnr: int) -> Optional[tuple[str, str, str]]:
    # API SatNOGS: devuelve JSON con TLEs
    url = f"https://db.satnogs.org/api/tle/?norad_cat_id={catnr}"
    try:
        r = httpx.get(url, timeout=10.0)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None

        item = data[0]

        # Hay variantes; soportamos varias
        name = None
        if isinstance(item.get("satellite"), dict):
            name = item["satellite"].get("name")
        name = name or f"CATNR {catnr}"

        # Intento de llaves posibles
        if "tle1" in item and "tle2" in item:
            line1, line2 = item["tle1"], item["tle2"]
        elif "tle0" in item and "tle1" in item:
            # algunos devuelven 2 líneas como tle0/tle1
            line1, line2 = item["tle0"], item["tle1"]
        elif "tle" in item and isinstance(item["tle"], str):
            parts = [ln.strip() for ln in item["tle"].splitlines() if ln.strip()]
            if len(parts) >= 2:
                line1, line2 = parts[0], parts[1]
            else:
                return None
        else:
            return None

        if not str(line1).startswith("1 ") or not str(line2).startswith("2 "):
            return None

        # validación catnr
        found = _parse_catnr_from_line1(str(line1))
        if found != catnr:
            return None

        return name, str(line1), str(line2)
    except Exception:
        return None


def refresh_tle_best_effort(catnr: int) -> bool:
    """
    Intenta refrescar TLE online. Devuelve True si actualizó, False si no pudo.
    """
    now = _now_utc()
    last = _LAST_REFRESH_ATTEMPT.get(catnr)
    if last and (now - last) < _REFRESH_COOLDOWN:
        return False
    _LAST_REFRESH_ATTEMPT[catnr] = now

    # 1) SatNOGS
    satnogs = _fetch_tle_from_satnogs(catnr)
    if satnogs:
        name, line1, line2 = satnogs
        _atomic_write_tle(catnr, name, line1, line2)
        _write_meta(catnr, source="satnogs")
        return True

    # 2) CelesTrak (gp.php)
    cel = _fetch_tle_from_celestrak(catnr)
    if cel:
        name, line1, line2 = cel
        _atomic_write_tle(catnr, name, line1, line2)
        _write_meta(catnr, source="celestrak")
        return True

    return False



def get_satellite_by_key(key: str, allow_network: bool = True) -> Tuple[str, int, EarthSatellite]:
    k = key.strip().upper()
    if k not in SATELLITES:
        raise ValueError(f"Satélite inválido '{key}'. Opciones: {list(SATELLITES.keys())}")

    catnr = SATELLITES[k]

    # auto-refresh si está viejo
    if allow_network and _needs_refresh(catnr):
        refresh_tle_best_effort(catnr)

    p = _tle_path(catnr)
    if not p.exists():
        raise ValueError(f"No existe TLE local para {k}. Creá: {p}")

    tle = _read_tle_file(p, catnr)
    sat = EarthSatellite(tle.line1, tle.line2, tle.name, ts)
    return k, catnr, sat

def refresh_tle_or_raise(catnr: int) -> None:
    """
    Fuerza refresh. Si no puede, levanta error para devolver 503.
    """
    ok = refresh_tle_best_effort(catnr)
    if not ok:
        raise ValueError(f"No pude refrescar TLE online para CATNR={catnr} (fuentes no disponibles)")

def read_meta_public(catnr: int) -> Optional[dict]:
    return _read_meta(catnr)

def tle_file_exists(catnr: int) -> bool:
    return _tle_path(catnr).exists()

def tle_file_mtime_utc(catnr: int) -> Optional[str]:
    p = _tle_path(catnr)
    if not p.exists():
        return None
    mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    return mtime.isoformat()

def tle_age_seconds(catnr: int) -> Optional[int]:
    meta = _read_meta(catnr)
    if meta and meta.get("fetched_at_utc"):
        try:
            fetched = datetime.fromisoformat(meta["fetched_at_utc"])
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=timezone.utc)
            return int((_now_utc() - fetched).total_seconds())
        except Exception:
            pass

    # fallback: mtime si no hay meta
    p = _tle_path(catnr)
    if not p.exists():
        return None
    mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    return int((_now_utc() - mtime).total_seconds())

def is_stale(catnr: int) -> bool:
    age = tle_age_seconds(catnr)
    if age is None:
        return True
    return age > int(TLE_TTL.total_seconds())

def _parse_tle_text_any(text: str, catnr: int) -> Optional[tuple[str, str, str]]:
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
            found = _parse_catnr_from_line1(line1)
        except Exception:
            continue

        if found != catnr:
            continue

        line2 = lines[i + 1]
        if not line2.startswith("2 "):
            continue

        name = lines[i - 1] if i - 1 >= 0 else f"CATNR {catnr}"
        return name, line1, line2

    return None


def _fetch_tle_from_celestrak(catnr: int) -> Optional[tuple[str, str, str]]:
    """
    CelesTrak (texto plano):
    https://celestrak.org/NORAD/elements/gp.php?CATNR=<catnr>&FORMAT=TLE
    """
    headers = {
        "User-Agent": "sat-uy/0.1 (FastAPI; local-dev)",
        "Accept": "text/plain,*/*",
    }

    urls = [
        f"https://celestrak.org/NORAD/elements/gp.php?CATNR={catnr}&FORMAT=TLE",
        # fallback (por si alguna red resuelve mejor el .com)
        f"https://celestrak.com/NORAD/elements/gp.php?CATNR={catnr}&FORMAT=TLE",
    ]

    try:
        with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
            for url in urls:
                resp = client.get(url)
                if resp.status_code == 403:
                    continue
                resp.raise_for_status()

                parsed = _parse_tle_text_any(resp.text, catnr)
                if parsed:
                    name, line1, line2 = parsed
                    return name, line1, line2

        return None
    except Exception:
        return None
