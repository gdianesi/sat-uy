# 🇺🇾 sat-uy — Uruguay Satellite Tracker

Full-stack web application to **predict and visualize satellite passes over Uruguay (Montevideo)** and display **ground tracks and current position** on an interactive map.

Built as a clean, modular project with a Python/FastAPI backend for orbital calculations and a React/TypeScript frontend for visualization.

---

## ✨ Highlights

- 🛰️ **Pass predictions**: rise / culmination / set and maximum elevation for a configurable time window  
- 🗺️ **Interactive map**: displays the **ground track** (GeoJSON LineString) for a selected pass  
- 📍 **Current position** endpoint to track a satellite “now”  
- 🕒 **Timezone aware**: returns UTC timestamps and local time (**America/Montevideo**)  
- 🧰 **Local TLE fallback** (`backend/data/`): the app can work even if external TLE sources fail

---

## 🧱 Architecture

This repository contains two projects:

- **backend/** → FastAPI REST API (orbital computations, TLE handling)
- **frontend/** → React + TypeScript + Vite UI (table + map visualization)

The frontend consumes JSON/GeoJSON responses from the backend to render passes and tracks.

---

## 🧰 Tech Stack

### Backend
- **Python**
- **FastAPI**
- **Skyfield** (orbit computations)
- Services/Routes structure for separation of concerns

### Frontend
- **React + TypeScript**
- **Vite**
- **Leaflet / React-Leaflet** (map visualization)
