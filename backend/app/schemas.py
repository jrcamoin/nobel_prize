from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CompoundCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    smiles: str = Field(min_length=1)
    target_pathogen: str = Field(min_length=1, max_length=160)
    activity_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    status: str = Field(default="predicted", max_length=40)
    evidence_source: str = Field(min_length=1, max_length=255)


class CompoundRead(CompoundCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HealthRead(BaseModel):
    status: str
    service: str
