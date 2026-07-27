from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .database import Base, engine, get_db
from .models import Compound
from .schemas import CompoundCreate, CompoundRead, HealthRead

settings = get_settings()
DatabaseSession = Annotated[Session, Depends(get_db)]


def seed_demo_compound(db: Session) -> None:
    if db.scalar(select(Compound.id).limit(1)) is not None:
        return
    db.add(
        Compound(
            name="Demo compound A",
            smiles="CC1=CC(=O)NC(=O)N1",
            target_pathogen="Acinetobacter baumannii",
            activity_score=0.82,
            confidence=0.68,
            status="needs validation",
            evidence_source="Illustrative seed data",
        )
    )
    db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        seed_demo_compound(db)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
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
    query = select(Compound).order_by(Compound.activity_score.desc()).limit(limit)
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
    compound = Compound(**payload.model_dump())
    db.add(compound)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="A compound with this name already exists"
        ) from exc
    db.refresh(compound)
    return compound
