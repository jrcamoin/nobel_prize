import hashlib
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .artifacts import upload_artifact
from .benchmark import train_baseline
from .chemistry import InvalidSmilesError, normalize_smiles
from .config import get_settings
from .database import SessionLocal, get_db
from .models import (
    CandidatePool,
    Compound,
    Dataset,
    Experiment,
    Job,
    LaboratoryProtocol,
    ModelRun,
    PoolCandidate,
    Prediction,
    Preregistration,
)
from .prospective import create_pool, preregister_pool, qualify_pool
from .schemas import (
    CandidateEvidenceUpdate,
    CandidatePoolCreate,
    CompoundCreate,
    CompoundDetail,
    CompoundRead,
    DatasetRead,
    ExperimentCreate,
    HealthRead,
    LaboratoryProtocolCreate,
    ModelRunRead,
)

settings = get_settings()
DatabaseSession = Annotated[Session, Depends(get_db)]


def require_write_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    if settings.api_write_key and x_api_key != settings.api_write_key:
        raise HTTPException(status_code=401, detail="Valid X-API-Key required")


WriteAccess = Annotated[None, Depends(require_write_key)]


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Schema changes are applied explicitly with Alembic.
    yield


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthRead, tags=["system"])
def health() -> HealthRead:
    return HealthRead(status="ok", service=settings.app_name)


@app.get("/api/compounds", response_model=list[CompoundRead], tags=["compounds"])
def list_compounds(
    db: DatabaseSession,
    pathogen: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[Compound]:
    query = select(Compound).order_by(Compound.activity_score.desc().nullslast()).limit(limit)
    if pathogen:
        query = query.where(Compound.target_pathogen == pathogen)
    return list(db.scalars(query))


@app.get("/api/compounds/{compound_id}", response_model=CompoundDetail, tags=["compounds"])
def get_compound(compound_id: int, db: DatabaseSession) -> Compound:
    compound = db.scalar(
        select(Compound)
        .options(selectinload(Compound.measurements))
        .where(Compound.id == compound_id)
    )
    if compound is None:
        raise HTTPException(status_code=404, detail="Compound not found")
    return compound


@app.post(
    "/api/compounds",
    response_model=CompoundRead,
    status_code=status.HTTP_201_CREATED,
    tags=["compounds"],
)
def create_compound(payload: CompoundCreate, db: DatabaseSession, _: WriteAccess) -> Compound:
    try:
        chemistry = normalize_smiles(payload.smiles)
    except InvalidSmilesError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    compound = Compound(
        **payload.model_dump(),
        **chemistry.__dict__,
        activity_score=None,
        confidence=None,
        status="unscored",
    )
    db.add(compound)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="This molecular structure already exists"
        ) from exc
    db.refresh(compound)
    return compound


@app.get("/api/datasets", response_model=list[DatasetRead], tags=["evidence"])
def list_datasets(db: DatabaseSession) -> list[Dataset]:
    return list(db.scalars(select(Dataset).order_by(Dataset.imported_at.desc())))


@app.get("/api/model-runs", response_model=list[ModelRunRead], tags=["evidence"])
def list_model_runs(db: DatabaseSession) -> list[ModelRun]:
    return list(db.scalars(select(ModelRun).order_by(ModelRun.created_at.desc())))


@app.get("/api/model-runs/{run_id}/report", tags=["evidence"])
def model_run_report(run_id: int, db: DatabaseSession) -> dict:
    run = db.get(ModelRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Model run not found")
    predictions = db.execute(
        select(Prediction, Compound)
        .join(Compound, Compound.id == Prediction.compound_id)
        .where(Prediction.model_run_id == run_id)
        .order_by(Prediction.activity_probability.desc())
    ).all()
    return {
        "model_run": {
            "id": run.id,
            "name": run.name,
            "algorithm": run.algorithm,
            "split_strategy": run.split_strategy,
            "random_seed": run.random_seed,
            "parameters": run.parameters,
            "metrics": run.metrics,
            "artifact_sha256": run.artifact_sha256,
            "git_commit": run.git_commit,
        },
        "dataset": {
            "name": run.dataset.name,
            "source_url": run.dataset.source_url,
            "license": run.dataset.license,
            "sha256": run.dataset.sha256,
        },
        "predictions": [
            {
                "compound_id": compound.id,
                "name": compound.name,
                "inchikey": compound.inchikey,
                "activity_probability": prediction.activity_probability,
                "confidence": prediction.confidence,
                "uncertainty": prediction.uncertainty,
            }
            for prediction, compound in predictions
        ],
    }


def _pool_payload(db: Session, pool: CandidatePool) -> dict:
    candidates = db.execute(
        select(PoolCandidate, Compound)
        .join(Compound, Compound.id == PoolCandidate.compound_id)
        .where(PoolCandidate.pool_id == pool.id)
        .order_by(PoolCandidate.rank)
    ).all()
    registration = db.scalar(select(Preregistration).where(Preregistration.pool_id == pool.id))
    protocol = db.scalar(select(LaboratoryProtocol).where(LaboratoryProtocol.pool_id == pool.id))
    return {
        "id": pool.id,
        "name": pool.name,
        "model_run_id": pool.model_run_id,
        "content_sha256": pool.content_sha256,
        "screening_rules": pool.screening_rules,
        "locked_at": pool.locked_at,
        "preregistration": (
            {
                "id": registration.id,
                "report_sha256": registration.report_sha256,
                "signature": registration.signature,
                "signed_at": registration.signed_at,
            }
            if registration
            else None
        ),
        "protocol": (
            {
                "id": protocol.id,
                "strain": protocol.strain,
                "method": protocol.method,
                "laboratory": protocol.laboratory,
                "protocol_sha256": protocol.protocol_sha256,
            }
            if protocol
            else None
        ),
        "candidates": [
            {
                "id": item.id,
                "compound_id": compound.id,
                "name": compound.name,
                "inchikey": compound.inchikey,
                "rank": item.rank,
                "passed_screen": item.passed_screen,
                "rejection_reasons": item.rejection_reasons,
                "properties": item.properties,
                "selected": item.selected,
                "availability_status": item.availability_status,
                "vendor": item.vendor,
                "catalog_number": item.catalog_number,
                "price": item.price,
                "purity": item.purity,
            }
            for item, compound in candidates
        ],
    }


@app.get("/api/candidate-pools", tags=["prospective"])
def list_candidate_pools(db: DatabaseSession) -> list[dict]:
    pools = list(db.scalars(select(CandidatePool).order_by(CandidatePool.created_at.desc())))
    return [_pool_payload(db, pool) for pool in pools]


@app.post("/api/candidate-pools", status_code=201, tags=["prospective"])
def create_candidate_pool(
    payload: CandidatePoolCreate, db: DatabaseSession, _: WriteAccess
) -> dict:
    try:
        pool = create_pool(db, payload.name, payload.model_run_id, payload.compound_ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _pool_payload(db, pool)


@app.post("/api/candidate-pools/{pool_id}/qualify", tags=["prospective"])
def qualify_candidate_pool(pool_id: int, db: DatabaseSession, _: WriteAccess) -> dict:
    try:
        pool = qualify_pool(db, pool_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _pool_payload(db, pool)


@app.patch("/api/candidate-pools/{pool_id}/candidates/{candidate_id}", tags=["prospective"])
def update_candidate_evidence(
    pool_id: int,
    candidate_id: int,
    payload: CandidateEvidenceUpdate,
    db: DatabaseSession,
    _: WriteAccess,
) -> dict:
    pool = db.get(CandidatePool, pool_id)
    if pool is None or pool.locked_at:
        raise HTTPException(status_code=422, detail="Candidate pool not editable")
    candidate = db.scalar(
        select(PoolCandidate).where(
            PoolCandidate.pool_id == pool_id, PoolCandidate.id == candidate_id
        )
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if payload.availability_status == "confirmed" and not (
        payload.vendor and payload.catalog_number and payload.purity is not None
    ):
        raise HTTPException(
            status_code=422,
            detail="Confirmed availability requires vendor, catalog number, and purity",
        )
    candidate.selected = payload.selected
    candidate.availability_status = payload.availability_status
    candidate.vendor = payload.vendor
    candidate.catalog_number = payload.catalog_number
    candidate.price = payload.price
    candidate.purity = payload.purity
    candidate.properties = {
        **candidate.properties,
        "cytotoxicity_evidence": payload.cytotoxicity_evidence or "not_available",
        "cytotoxicity_source": payload.cytotoxicity_source,
    }
    db.commit()
    return _pool_payload(db, pool)


@app.put("/api/candidate-pools/{pool_id}/protocol", tags=["prospective"])
def set_laboratory_protocol(
    pool_id: int,
    payload: LaboratoryProtocolCreate,
    db: DatabaseSession,
    _: WriteAccess,
) -> dict:
    pool = db.get(CandidatePool, pool_id)
    if pool is None or pool.locked_at:
        raise HTTPException(status_code=422, detail="Candidate pool not editable")
    if payload.concentration_max <= payload.concentration_min:
        raise HTTPException(status_code=422, detail="Maximum concentration must exceed minimum")
    values = payload.model_dump()
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    protocol = db.scalar(select(LaboratoryProtocol).where(LaboratoryProtocol.pool_id == pool_id))
    if protocol is None:
        protocol = LaboratoryProtocol(pool_id=pool_id, **values, protocol_sha256=digest)
        db.add(protocol)
    else:
        for key, value in values.items():
            setattr(protocol, key, value)
        protocol.protocol_sha256 = digest
    db.commit()
    db.refresh(protocol)
    return {"id": protocol.id, "pool_id": pool_id, **values, "protocol_sha256": digest}


@app.post("/api/candidate-pools/{pool_id}/preregister", tags=["prospective"])
def preregister_candidate_pool(pool_id: int, db: DatabaseSession, _: WriteAccess) -> dict:
    try:
        registration = preregister_pool(db, pool_id, settings.preregistration_signing_key)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "id": registration.id,
        "pool_id": registration.pool_id,
        "report": registration.report,
        "report_sha256": registration.report_sha256,
        "signature": registration.signature,
        "signed_at": registration.signed_at,
    }


@app.post("/api/experiments", status_code=201, tags=["experiments"])
def create_experiment(payload: ExperimentCreate, db: DatabaseSession, _: WriteAccess) -> dict:
    registration = db.get(Preregistration, payload.preregistration_id)
    if registration is None:
        raise HTTPException(status_code=422, detail="Preregistration not found")
    candidate = db.scalar(
        select(PoolCandidate).where(
            PoolCandidate.pool_id == registration.pool_id,
            PoolCandidate.compound_id == payload.compound_id,
        )
    )
    if candidate is None:
        raise HTTPException(status_code=422, detail="Compound is not in the preregistered pool")
    experiment = Experiment(**payload.model_dump())
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return {
        "id": experiment.id,
        "compound_id": experiment.compound_id,
        "preregistration_id": experiment.preregistration_id,
        "status": experiment.status,
        "result": experiment.result,
    }


def _run_training_job(job_id: int, dataset_id: int, seed: int) -> None:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        job.status = "running"
        job.started_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()
        try:
            run = train_baseline(db, dataset_id, Path("artifacts"), seed)
            artifact_path = Path("artifacts") / f"baseline-dataset-{dataset_id}.joblib"
            artifact_uri = upload_artifact(artifact_path, settings)
            job = db.get(Job, job_id)
            job.status = "completed"
            job.result = {
                "model_run_id": run.id,
                "metrics": run.metrics,
                "artifact_uri": artifact_uri,
            }
        except Exception as exc:  # noqa: BLE001 - job boundary must persist failures
            db.rollback()
            job = db.get(Job, job_id)
            job.status = "failed"
            job.error = str(exc)
        job.finished_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()


@app.get("/api/jobs", tags=["jobs"])
def list_jobs(db: DatabaseSession) -> list[dict]:
    jobs = list(db.scalars(select(Job).order_by(Job.created_at.desc()).limit(100)))
    return [
        {
            "id": job.id,
            "job_type": job.job_type,
            "status": job.status,
            "parameters": job.parameters,
            "result": job.result,
            "error": job.error,
            "created_at": job.created_at,
        }
        for job in jobs
    ]


@app.post("/api/jobs/train/{dataset_id}", status_code=202, tags=["jobs"])
def enqueue_training(
    dataset_id: int,
    background_tasks: BackgroundTasks,
    db: DatabaseSession,
    _: WriteAccess,
    seed: int = 17,
) -> dict:
    if db.get(Dataset, dataset_id) is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    job = Job(
        job_type="train_baseline",
        status="queued",
        parameters={"dataset_id": dataset_id, "seed": seed},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(_run_training_job, job.id, dataset_id, seed)
    return {"id": job.id, "status": job.status}
