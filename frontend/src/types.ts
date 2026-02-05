// src/types.ts
import type { Feature, LineString } from "geojson";

export type SatelliteInfo = { key: string; catnr: number };

export type SatelliteItem = {
  key: string;
  catnr: number;
  has_local?: boolean;
  stale?: boolean;
};

export type Pass = {
  rise_utc: string;
  set_utc: string;
  rise_uy: string;
  culmination_uy: string;
  set_uy: string;
  max_elevation_deg: number;
};

export type PassesResponse = {
  satellite: SatelliteInfo;
  passes: Pass[];
  start_utc: string;
  end_utc: string;
};

export type TrackFeature = Feature<LineString>;
export type TrackResponse = { geojson: TrackFeature };

export type SatellitesResponse = {
  satellites: SatelliteItem[];
};

export type PositionResponse = {
  satellite: SatelliteInfo;
  t_utc: string;
  t_uy: string;
  position: { lat: number; lon: number; alt_km: number };
};
