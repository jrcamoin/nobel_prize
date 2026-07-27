import hashlib
import hmac
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import AllChem, Crippen, Descriptors, Lipinski
from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CandidatePool, Compound, ModelRun, PoolCandidate, Prediction, Preregistration

SCREENING_RULES = {
    "molecular_weight_max": 600.0,
    "logp_max": 5.0,
    "h_bond_donors_max": 5,
    "h_bond_acceptors_max": 10,
    "pains_allowed": False,
}


def _fingerprint(smiles: str) -> np.ndarray:
    molecule = Chem.MolFromSmiles(smiles)
    fingerprint = AllChem.GetMorganGenerator(radius=2, fpSize=2048).GetFingerprint(molecule)
    array = np.zeros((2048,), dtype=np.uint8)
    DataStructs.ConvertToNumpyArray(fingerprint, array)
    return array


def screen_compound(compound: Compound) -> tuple[dict[str, Any], list[str]]:
    molecule = Chem.MolFromSmiles(compound.canonical_smiles)
    properties = {
        "molecular_weight": round(Descriptors.MolWt(molecule), 3),
        "logp": round(Crippen.MolLogP(molecule), 3),
        "h_bond_donors": Lipinski.NumHDonors(molecule),
        "h_bond_acceptors": Lipinski.NumHAcceptors(molecule),
    }
    params = FilterCatalogParams()
    params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
    alert = FilterCatalog(params).GetFirstMatch(molecule)
    properties["pains_alert"] = alert.GetDescription() if alert else None
    reasons: list[str] = []
    if properties["molecular_weight"] > SCREENING_RULES["molecular_weight_max"]:
        reasons.append("molecular_weight")
    if properties["logp"] > SCREENING_RULES["logp_max"]:
        reasons.append("logp")
    if properties["h_bond_donors"] > SCREENING_RULES["h_bond_donors_max"]:
        reasons.append("h_bond_donors")
    if properties["h_bond_acceptors"] > SCREENING_RULES["h_bond_acceptors_max"]:
        reasons.append("h_bond_acceptors")
    if alert:
        reasons.append("pains_alert")
    return properties, reasons


def create_pool(
    db: Session, name: str, model_run_id: int, compound_ids: list[int]
) -> CandidatePool:
    run = db.get(ModelRun, model_run_id)
    if run is None:
        raise ValueError("Model run not found")
    compounds = list(db.scalars(select(Compound).where(Compound.id.in_(set(compound_ids)))))
    if len(compounds) != len(set(compound_ids)):
        raise ValueError("One or more compounds were not found")
    identities = sorted(compound.inchikey for compound in compounds)
    payload = f"{model_run_id}\n" + "\n".join(identities)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    pool = CandidatePool(
        name=name,
        model_run_id=model_run_id,
        content_sha256=digest,
        screening_rules=SCREENING_RULES,
    )
    db.add(pool)
    db.flush()
    prediction_scores = dict(
        db.execute(
            select(Prediction.compound_id, Prediction.activity_probability).where(
                Prediction.model_run_id == model_run_id,
                Prediction.compound_id.in_(compound_ids),
            )
        ).all()
    )
    artifact = Path("artifacts") / f"baseline-dataset-{run.dataset_id}.joblib"
    if artifact.exists():
        model = joblib.load(artifact)["model"]
        unscored = [compound for compound in compounds if compound.id not in prediction_scores]
        if unscored:
            probabilities = model.predict_proba(
                np.stack([_fingerprint(item.canonical_smiles) for item in unscored])
            )[:, 1]
            prediction_scores.update(
                {
                    compound.id: float(probability)
                    for compound, probability in zip(unscored, probabilities, strict=True)
                }
            )
    ranked = sorted(
        compounds, key=lambda compound: prediction_scores.get(compound.id, -1), reverse=True
    )
    for rank, compound in enumerate(ranked, start=1):
        properties, reasons = screen_compound(compound)
        properties["activity_probability"] = prediction_scores.get(compound.id)
        db.add(
            PoolCandidate(
                pool_id=pool.id,
                compound_id=compound.id,
                passed_screen=not reasons,
                rejection_reasons=reasons,
                properties=properties,
                rank=rank,
            )
        )
    db.commit()
    db.refresh(pool)
    return pool


def preregister_pool(db: Session, pool_id: int, signing_key: str) -> Preregistration:
    if not signing_key:
        raise ValueError("PREREGISTRATION_SIGNING_KEY is not configured")
    pool = db.get(CandidatePool, pool_id)
    if pool is None:
        raise ValueError("Candidate pool not found")
    existing = db.scalar(select(Preregistration).where(Preregistration.pool_id == pool_id))
    if existing:
        return existing
    candidates = list(
        db.scalars(
            select(PoolCandidate)
            .where(PoolCandidate.pool_id == pool_id)
            .order_by(PoolCandidate.rank)
        )
    )
    report = {
        "schema_version": 1,
        "pool_id": pool.id,
        "pool_sha256": pool.content_sha256,
        "model_run_id": pool.model_run_id,
        "screening_rules": pool.screening_rules,
        "candidates": [
            {
                "compound_id": item.compound_id,
                "rank": item.rank,
                "passed_screen": item.passed_screen,
                "rejection_reasons": item.rejection_reasons,
                "properties": item.properties,
            }
            for item in candidates
        ],
    }
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    signature = hmac.new(signing_key.encode(), encoded, hashlib.sha256).hexdigest()
    pool.locked_at = datetime.now(UTC).replace(tzinfo=None)
    registration = Preregistration(
        pool_id=pool.id,
        report=report,
        report_sha256=digest,
        signature=signature,
    )
    db.add(registration)
    db.commit()
    db.refresh(registration)
    return registration
