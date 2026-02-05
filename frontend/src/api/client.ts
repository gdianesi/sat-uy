const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function apiGet<T>(path: string, params?: Record<string, string>) {
  const url = new URL(path, BASE_URL);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  }

  const r = await fetch(url.toString());
  if (!r.ok) {
    const txt = await r.text().catch(() => "");
    throw new Error(`HTTP ${r.status} ${txt}`.trim());
  }
  return (await r.json()) as T;
}
