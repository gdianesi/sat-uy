import { useEffect, useMemo, useRef, useState } from "react";
import TrackMap from "./components/TrackMap";
import { apiGet } from "./api/client";
import "./styles/theme.css";
import "./App.css";

import type {
  Pass,
  PassesResponse,
  PositionResponse,
  SatellitesResponse,
  SatelliteItem,
  TrackFeature,
  TrackResponse,
} from "./types";

const HOURS = 48;
const MIN_ELEV = 10;
const STEP_SECONDS = 10;

const ORBIT_MINUTES = 96;          // 1 vuelta aprox (ISS ~ 92-96min)
const ORBIT_REFRESH_MS = 30_000;   // refrescar órbita cada 30s
const PASSES_REFRESH_MS = 60_000;  // refrescar pasadas cada 60s

function ms(iso: string): number {
  return new Date(iso).getTime();
}

function pickAutoPass(passes: Pass[], nowMs: number): Pass | null {
  if (!passes?.length) return null;

  // Aseguramos orden por rise_utc por si el backend no lo garantiza
  const sorted = [...passes].sort((a, b) => ms(a.rise_utc) - ms(b.rise_utc));

  // “activa o próxima”: primera cuyo set está en el futuro
  const candidate = sorted.find((p) => ms(p.set_utc) > nowMs);
  return candidate ?? null;
}

export default function App() {
  const [satellites, setSatellites] = useState<SatelliteItem[]>([]);
  const [satKey, setSatKey] = useState<string>("ISS");

  const [data, setData] = useState<PassesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [selectedPass, setSelectedPass] = useState<Pass | null>(null);
  const [trackGeoJson, setTrackGeoJson] = useState<TrackFeature | null>(null);
  const [orbitGeoJson, setOrbitGeoJson] = useState<TrackFeature | null>(null);

  // realtime position
  const [position, setPosition] = useState<PositionResponse | null>(null);

  const passesIntervalRef = useRef<number | null>(null);

  // Load satellites once
  useEffect(() => {
    (async () => {
      try {
        const res = await apiGet<SatellitesResponse>("/satellites");
        setSatellites(res.satellites);

        // Si existe ISS en la lista, nos quedamos con ISS; si no, usamos el primero
        const keys = new Set((res.satellites ?? []).map((s) => s.key));
        if (keys.has("ISS")) setSatKey("ISS");
        else if (res.satellites?.length) setSatKey(res.satellites[0].key);
      } catch (e) {
        setError(String(e));
      }
    })();
  }, []);

  async function loadPasses(opts?: { resetSelection?: boolean }) {
    const resetSelection = opts?.resetSelection ?? false;

    setError(null);

    const params: Record<string, string> = {
      satellite: satKey,
      hours: String(HOURS),
      min_elevation_deg: String(MIN_ELEV),
      // start_utc NO se manda -> backend usa “ahora”
    };

    try {
      const json = await apiGet<PassesResponse>("/passes", params);
      setData(json);

      const nowMs = Date.now();

      // Si NO reseteamos selección y la seleccionada actual sigue vigente, la mantenemos
      if (!resetSelection && selectedPass && ms(selectedPass.set_utc) > nowMs) {
        // pero actualizamos el objeto si cambió (match por rise_utc+set_utc)
        const updated = json.passes.find(
          (p) => p.rise_utc === selectedPass.rise_utc && p.set_utc === selectedPass.set_utc
        );
        if (updated) setSelectedPass(updated);
        return;
      }

      // Si reseteamos o la actual ya terminó -> auto-selección
      const auto = pickAutoPass(json.passes, nowMs);
      setSelectedPass(auto);
      setTrackGeoJson(null); // se vuelve a pedir cuando selectedPass cambie
    } catch (e) {
      setError(String(e));
    }
  }

  // load passes when sat changes (y resetea selección)
  useEffect(() => {
    if (!satKey) return;

    setData(null);
    setSelectedPass(null);
    setTrackGeoJson(null);

    loadPasses({ resetSelection: true });

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [satKey]);

  // auto refresh passes (modo “tiempo real”)
  useEffect(() => {
    if (!satKey) return;

    if (passesIntervalRef.current) window.clearInterval(passesIntervalRef.current);

    passesIntervalRef.current = window.setInterval(() => {
      loadPasses({ resetSelection: false });
    }, PASSES_REFRESH_MS);

    return () => {
      if (passesIntervalRef.current) window.clearInterval(passesIntervalRef.current);
      passesIntervalRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [satKey, selectedPass?.rise_utc, selectedPass?.set_utc]);

  // track for selected pass (rise->set)
  useEffect(() => {
    if (!selectedPass) return;

    (async () => {
      try {
        setError(null);
        setTrackGeoJson(null);

        const json = await apiGet<TrackResponse>("/track", {
          satellite: satKey,
          start_utc: selectedPass.rise_utc,
          end_utc: selectedPass.set_utc,
          step_seconds: String(STEP_SECONDS),
        });

        setTrackGeoJson(json.geojson);
      } catch (e) {
        setError(String(e));
      }
    })();
  }, [selectedPass, satKey]);

  // orbit “general” (track/now)
  useEffect(() => {
    if (!satKey) return;

    let alive = true;

    async function loadOrbit() {
      try {
        const res = await apiGet<TrackResponse>("/track/now", {
          satellite: satKey,
          minutes: String(ORBIT_MINUTES),
          step_seconds: String(STEP_SECONDS),
        });

        if (alive) setOrbitGeoJson(res.geojson);
      } catch (e) {
        console.warn("orbit failed:", e);
      }
    }

    loadOrbit(); // inmediato
    const id = window.setInterval(loadOrbit, ORBIT_REFRESH_MS);

    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [satKey]);

  // realtime: poll /position
  useEffect(() => {
    let alive = true;
    let first = true;

    async function tick() {
      try {
        const p = await apiGet<PositionResponse>("/position", { satellite: satKey });
        if (alive) setPosition(p);
      } catch (err) {
        if (first) console.warn("position failed:", err);
      } finally {
        first = false;
      }
    }

    tick();
    const id = window.setInterval(tick, 1500);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [satKey]);

  const headerTitle = useMemo(() => {
    const k = data?.satellite?.key ?? satKey;
    const c = data?.satellite?.catnr;
    return c ? `${k} (${c})` : k;
  }, [data, satKey]);

  if (error) {
    return (
      <div className="page">
        <div className="card error">Error: {error}</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="page">
        <div className="card">Cargando pasadas…</div>
      </div>
    );
  }

  return (
  <div className="page">
    <div className="shell">
      <div className="card">
        <div className="topbar">
          <div className="titleWrap">
            <h1 className="title">Pasadas — {headerTitle}</h1>
            <div className="subtitle">
              Predicción en vivo desde Uruguay · ventana {HOURS}h · min elev {MIN_ELEV}°
            </div>
          </div>

          <div className="statusRight">
            <div className="pill">
              <span className="liveDot" />
              LIVE
            </div>

            <div className="pill">
              {position ? (
                <>
                  {new Date(position.t_uy).toLocaleTimeString("es-UY")} ·{" "}
                  lat {position.position.lat.toFixed(2)} · lon {position.position.lon.toFixed(2)} ·{" "}
                  alt {position.position.alt_km.toFixed(0)} km
                </>
              ) : (
                "cargando posición…"
              )}
            </div>
          </div>
        </div>

        <div className="controls">
          <div className="leftControls">
            <label className="label">
              Satélite
              <select
                className="select"
                value={satKey}
                onChange={(e) => setSatKey(e.target.value)}
              >
                {satellites.map((s) => (
                  <option key={s.key} value={s.key}>
                    {s.key} ({s.catnr})
                  </option>
                ))}
              </select>
            </label>

            <div className="hint">
              {selectedPass
                ? "Auto: mostrando trayectoria visible (rise→set) de la pasada activa/próxima."
                : "Auto: no hay pasadas próximas en la ventana."}
            </div>
          </div>
        </div>

        <div className="grid">
          <div className="sidePanel">
            <div className="tableHead">
              <div className="tableTitle">Ventana de pasadas (UY)</div>
              <div className="tableTitle">click para ver</div>
            </div>

            <table className="table">
              <thead>
                <tr>
                  <th>Rise</th>
                  <th>Max</th>
                  <th>Set</th>
                </tr>
              </thead>

              <tbody>
                {data.passes.map((p, idx) => {
                  const selected =
                    selectedPass?.rise_utc === p.rise_utc && selectedPass?.set_utc === p.set_utc;

                  return (
                    <tr
                      key={idx}
                      className={selected ? "row selected" : "row"}
                      onClick={() => setSelectedPass(p)}
                    >
                      <td>{new Date(p.rise_uy).toLocaleString("es-UY")}</td>
                      <td>
                        <span className="elevBadge">{p.max_elevation_deg}°</span>
                      </td>
                      <td>{new Date(p.set_uy).toLocaleString("es-UY")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="mapPanel">
            <div className="mapInfo">
              <div className="kpi">
                <strong>Modo:</strong>{" "}
                {selectedPass ? "pasada visible (rise→set)" : "sin pasada próxima"}
              </div>

              <div className="kpi">
                <strong>Órbita:</strong> actualización cada {Math.round(ORBIT_REFRESH_MS / 1000)}s
              </div>
            </div>

            <TrackMap
              orbitGeojson={orbitGeoJson}
              passGeojson={trackGeoJson}
              position={position ? { lat: position.position.lat, lon: position.position.lon } : null}
            />
          </div>
        </div>
      </div>
    </div>
  </div>
);
}
