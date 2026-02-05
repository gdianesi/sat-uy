import { MapContainer, TileLayer, GeoJSON, Marker, useMap } from "react-leaflet";
import type { LatLngBoundsExpression, LatLngExpression } from "leaflet";
import type { TrackFeature } from "../types";
import { useEffect, useMemo } from "react";
import L from "leaflet";

import "leaflet/dist/leaflet.css";
import "../styles/TrackMap.css";

type Props = {
  orbitGeojson: TrackFeature | null;
  passGeojson: TrackFeature | null;
  position: { lat: number; lon: number } | null;
};

const URUGUAY_CENTER: LatLngExpression = [-34.9, -56.16];
const MVD: LatLngExpression = [-34.9011, -56.1645];

// icon simple sin imágenes
const satIcon = L.divIcon({
  className: "sat-icon",
  html: "🛰️",
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

function MapAutoFix({
  orbitGeojson,
  passGeojson,
}: {
  orbitGeojson: TrackFeature | null;
  passGeojson: TrackFeature | null;
}) {

  const map = useMap();

  useEffect(() => {
    const id = window.setTimeout(() => map.invalidateSize(), 50);
    return () => window.clearTimeout(id);
  }, [map]);

  useEffect(() => {
    const g = passGeojson ?? orbitGeojson; // prioridad: lo visible (rise->set)
    if (!g?.geometry?.coordinates?.length) return;

    const coords = g.geometry.coordinates;
    const bounds: LatLngBoundsExpression = coords.map(([lon, lat]) => [lat, lon]);

    map.fitBounds(bounds, { padding: [20, 20] });
  }, [orbitGeojson, passGeojson, map]);


  return null;
}

export default function TrackMap({ orbitGeojson, passGeojson, position }: Props) {
  const satLatLng = useMemo<LatLngExpression | null>(() => {
    if (!position) return null;
    return [position.lat, position.lon];
  }, [position]);

  return (
    <div className="mapShell">
      <MapContainer center={URUGUAY_CENTER} zoom={5} className="map">
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="© OpenStreetMap contributors"
        />

        <MapAutoFix orbitGeojson={orbitGeojson} passGeojson={passGeojson} />

        {/* marcador fijo Montevideo */}
        <Marker position={MVD} />

        {/* satélite en tiempo real */}
        {satLatLng && <Marker position={satLatLng} icon={satIcon} />}
        
        {orbitGeojson && (
          <GeoJSON
            key={`orbit-${orbitGeojson.properties?.catnr ?? "sat"}-${orbitGeojson.geometry.coordinates.length}`}
            data={orbitGeojson}
            style={{
              weight: 2.5,
              opacity: 0.35,
            }}
          />
        )}

        {passGeojson && (
          <GeoJSON
            key={`pass-${passGeojson.properties?.catnr ?? "sat"}-${passGeojson.geometry.coordinates.length}-${passGeojson.geometry.coordinates[0]?.join(",")}-${passGeojson.geometry.coordinates.at(-1)?.join(",")}`}
            data={passGeojson}
            style={{
              weight: 4,
              opacity: 0.95,
            }}
          />
        )}
      </MapContainer>
    </div>
  );
}
