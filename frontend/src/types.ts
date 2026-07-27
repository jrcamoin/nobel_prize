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

export type CompoundDetail = Compound & {
  canonical_smiles: string;
  inchikey: string;
  scaffold_smiles: string;
  molecular_weight: number;
  measurements: Array<{
    standard_type: string; relation: string | null; value: number; units: string; active: boolean;
  }>;
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
    comparisons?: Record<string, {
      average_precision: number; roc_auc: number; brier_score: number;
    }>;
    prospective_holdout?: {
      sha256: string; compound_count: number; frozen: boolean;
    };
  };
};
