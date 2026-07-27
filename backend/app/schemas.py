from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CompoundCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    smiles: str = Field(min_length=1)
    target_pathogen: str = Field(min_length=1, max_length=160)
    source_id: str | None = Field(default=None, max_length=80)
    evidence_source: str = Field(min_length=1, max_length=255)


class CompoundRead(CompoundCreate):
    id: int
    canonical_smiles: str
    inchikey: str
    scaffold_smiles: str
    molecular_weight: float
    activity_score: float | None
    confidence: float | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetRead(BaseModel):
    id: int
    name: str
    version: str
    source_url: str
    license: str
    sha256: str
    record_count: int
    imported_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelRunRead(BaseModel):
    id: int
    name: str
    algorithm: str
    split_strategy: str
    random_seed: int
    metrics: dict[str, Any]
    git_commit: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HealthRead(BaseModel):
    status: str
    service: str
