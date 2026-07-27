from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    version: Mapped[str] = mapped_column(String(80))
    source_url: Mapped[str] = mapped_column(Text)
    license: Mapped[str] = mapped_column(String(120))
    query: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    imported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    assays: Mapped[list["Assay"]] = relationship(back_populates="dataset")
    model_runs: Mapped[list["ModelRun"]] = relationship(back_populates="dataset")


class Assay(Base):
    __tablename__ = "assays"
    __table_args__ = (UniqueConstraint("dataset_id", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    external_id: Mapped[str] = mapped_column(String(80))
    organism: Mapped[str] = mapped_column(String(160), index=True)
    assay_type: Mapped[str | None] = mapped_column(String(40))
    description: Mapped[str | None] = mapped_column(Text)

    dataset: Mapped[Dataset] = relationship(back_populates="assays")
    measurements: Mapped[list["Measurement"]] = relationship(back_populates="assay")


class Compound(Base):
    __tablename__ = "compounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    source_id: Mapped[str | None] = mapped_column(String(80), index=True)
    smiles: Mapped[str] = mapped_column(Text)
    canonical_smiles: Mapped[str] = mapped_column(Text, unique=True)
    inchikey: Mapped[str] = mapped_column(String(27), unique=True, index=True)
    scaffold_smiles: Mapped[str] = mapped_column(Text)
    molecular_weight: Mapped[float] = mapped_column(Float)
    target_pathogen: Mapped[str] = mapped_column(String(160), index=True)
    activity_score: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(40), default="unscored")
    evidence_source: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    measurements: Mapped[list["Measurement"]] = relationship(back_populates="compound")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="compound")


class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (UniqueConstraint("assay_id", "compound_id", "standard_type", "value"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    compound_id: Mapped[int] = mapped_column(ForeignKey("compounds.id", ondelete="CASCADE"))
    assay_id: Mapped[int] = mapped_column(ForeignKey("assays.id", ondelete="CASCADE"))
    standard_type: Mapped[str] = mapped_column(String(40))
    relation: Mapped[str | None] = mapped_column(String(8))
    value: Mapped[float] = mapped_column(Float)
    units: Mapped[str] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(Boolean)

    compound: Mapped[Compound] = relationship(back_populates="measurements")
    assay: Mapped[Assay] = relationship(back_populates="measurements")


class ModelRun(Base):
    __tablename__ = "model_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"))
    name: Mapped[str] = mapped_column(String(160))
    algorithm: Mapped[str] = mapped_column(String(120))
    split_strategy: Mapped[str] = mapped_column(String(80))
    random_seed: Mapped[int] = mapped_column(Integer)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64))
    git_commit: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    dataset: Mapped[Dataset] = relationship(back_populates="model_runs")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="model_run")


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (UniqueConstraint("model_run_id", "compound_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    compound_id: Mapped[int] = mapped_column(ForeignKey("compounds.id", ondelete="CASCADE"))
    model_run_id: Mapped[int] = mapped_column(ForeignKey("model_runs.id", ondelete="CASCADE"))
    activity_probability: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    uncertainty: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    compound: Mapped[Compound] = relationship(back_populates="predictions")
    model_run: Mapped[ModelRun] = relationship(back_populates="predictions")


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(primary_key=True)
    compound_id: Mapped[int] = mapped_column(ForeignKey("compounds.id"))
    protocol_uri: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    performed_by: Mapped[str | None] = mapped_column(String(160))
    performed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
