import type { Compound } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function fetchCompounds(signal?: AbortSignal): Promise<Compound[]> {
  const response = await fetch(`${API_URL}/api/compounds`, { signal });
  if (!response.ok) {
    throw new Error(`API returned ${response.status}`);
  }
  return response.json() as Promise<Compound[]>;
}

