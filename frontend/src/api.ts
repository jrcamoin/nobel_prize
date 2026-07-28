import type {
  CandidatePool,
  Compound,
  CompoundDetail,
  Dataset,
  Evidence,
  Job,
  ModelRun,
} from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function fetchCompounds(signal?: AbortSignal): Promise<Compound[]> {
  const response = await fetch(`${API_URL}/api/compounds`, { signal });
  if (!response.ok) {
    throw new Error(`API returned ${response.status}`);
  }
  return response.json() as Promise<Compound[]>;
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { signal });
  if (!response.ok) throw new Error(`API returned ${response.status}`);
  return response.json() as Promise<T>;
}

export const fetchDatasets = (signal?: AbortSignal) =>
  get<Dataset[]>("/api/datasets", signal);

export const fetchModelRuns = (signal?: AbortSignal) =>
  get<ModelRun[]>("/api/model-runs", signal);

export const fetchCompound = (id: number, signal?: AbortSignal) =>
  get<CompoundDetail>(`/api/compounds/${id}`, signal);

export const fetchCompoundEvidence = (id: number, signal?: AbortSignal) =>
  get<Evidence[]>(`/api/compounds/${id}/evidence`, signal);

export const searchCompounds = (query: string, signal?: AbortSignal) =>
  get<Compound[]>(`/api/search?query=${encodeURIComponent(query)}`, signal);

export type Comparison = { compounds: Array<Compound & { evidence_count: number; active_evidence_count: number; molecular_weight: number; inchikey: string }> };
export const compareCompounds = (ids: number[]) => get<Comparison>(`/api/compare?ids=${ids.join(",")}`);
export const fetchPublicSources = (id: number) => get<{ links: Array<{ source: string; url: string; kind: string }> }>(`/api/compounds/${id}/public-sources`);

export const fetchCandidatePools = (signal?: AbortSignal) =>
  get<CandidatePool[]>("/api/candidate-pools", signal);

export const fetchJobs = (signal?: AbortSignal) =>
  get<Job[]>("/api/jobs", signal);
