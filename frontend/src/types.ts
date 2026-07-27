export type Compound = {
  id: number;
  name: string;
  smiles: string;
  target_pathogen: string;
  activity_score: number | null;
  confidence: number | null;
  status: string;
  evidence_source: string;
  created_at: string;
};

export type Dataset = {
  id: number; name: string; version: string; source_url: string; license: string;
  sha256: string; record_count: number; imported_at: string;
};

export type ModelRun = {
  id: number; name: string; algorithm: string; split_strategy: string;
  random_seed: number; git_commit: string | null; created_at: string;
  metrics: {
    average_precision?: number; roc_auc?: number; brier_score?: number;
    counts?: Record<string, number>; activity_definition?: string;
  };
};
