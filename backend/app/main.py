from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .chemistry import InvalidSmilesError, normalize_smiles
from .config import get_settings
from .database import get_db
from .models import Compound, Dataset, ModelRun
from .schemas import CompoundCreate, CompoundRead, DatasetRead, HealthRead, ModelRunRead

settings = get_settings()
DatabaseSession = Annotated[Session, Depends(get_db)]


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


@app.post(
    "/api/compounds",
    response_model=CompoundRead,
    status_code=status.HTTP_201_CREATED,
    tags=["compounds"],
)
def create_compound(payload: CompoundCreate, db: DatabaseSession) -> Compound:
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
