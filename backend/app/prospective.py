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

from .models import (
    Assay,
    CandidatePool,
    Compound,
    LaboratoryProtocol,
    Measurement,
    ModelRun,
    PoolCandidate,
    Prediction,
    Preregistration,
)

SCREENING_RULES = {
    "molecular_weight_max": 600.0,
    "logp_max": 5.0,
    "h_bond_donors_max": 5,
    "h_bond_acceptors_max": 10,
    "pains_allowed": False,
}

# Exact identities for common clinical antibiotics; analogues are handled by
# the active-training-set similarity check.
KNOWN_ANTIBIOTIC_INCHIKEYS = {
    "AVKUERGKIZMTKX-NJBDSQKTSA-N",  # ampicillin
    "CEAZRRDELHUEMR-URQXQFDESA-N",  # gentamicin
    "JQXXHWHPUNPDRT-WLSIYKJHSA-N",  # rifampicin
    "MYSWGUAQZAJSOK-UHFFFAOYSA-N",  # ciprofloxacin
    "OFVLGDICTFRJMM-WESIUVDSSA-N",  # tetracycline
    "WIIZWVCIJKGZOK-RKDXNWHRSA-N",  # chloramphenicol
    "XQTWDDCIUJNLTR-CVHRZJFOSA-N",  # doxycycline
}


def _fingerprint(smiles: str) -> np.ndarray:
    molecule = Chem.MolFromSmiles(smiles)
    fingerprint = AllChem.GetMorganGenerator(radius=2, fpSize=2048).GetFingerprint(molecule)
    array = np.zeros((2048,), dtype=np.uint8)
    DataStructs.ConvertToNumpyArray(fingerprint, array)
    return array


def _rdkit_fingerprint(smiles: str):
    return AllChem.GetMorganGenerator(radius=2, fpSize=2048).GetFingerprint(
        Chem.MolFromSmiles(smiles)
    )


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
    pains_catalog = FilterCatalog(params)
    alert = pains_catalog.GetFirstMatch(molecule)
    properties["pains_alert"] = alert.GetDescription() if alert else None
    liability_params = FilterCatalogParams()
    liability_params.AddCatalog(FilterCatalogParams.FilterCatalogs.BRENK)
    liabilities = [
        match.GetDescription() for match in FilterCatalog(liability_params).GetMatches(molecule)
    ]
    properties["reactive_alerts"] = liabilities
    properties["solubility_risk"] = (
        "high"
        if properties["logp"] > 4 or properties["molecular_weight"] > 500
        else "moderate"
        if properties["logp"] > 3
        else "low"
    )
    properties["known_antibiotic_exact_match"] = compound.inchikey in KNOWN_ANTIBIOTIC_INCHIKEYS
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
    if liabilities:
        reasons.append("reactive_alert")
    if properties["known_antibiotic_exact_match"]:
        reasons.append("known_antibiotic")
    return properties, reasons


def qualify_pool(db: Session, pool_id: int, similarity_threshold: float = 0.7) -> CandidatePool:
    pool = db.get(CandidatePool, pool_id)
    if pool is None:
        raise ValueError("Candidate pool not found")
    if pool.locked_at:
        raise ValueError("Candidate pool is locked")
    run = db.get(ModelRun, pool.model_run_id)
    training_compounds = list(
        db.scalars(
            select(Compound)
            .join(Measurement)
            .join(Assay)
            .where(Assay.dataset_id == run.dataset_id)
            .distinct()
        )
    )
    training_fingerprints = [
        _rdkit_fingerprint(compound.canonical_smiles) for compound in training_compounds
    ]
    active_fingerprints = [
        _rdkit_fingerprint(compound.canonical_smiles)
        for compound in db.scalars(
            select(Compound)
            .join(Measurement)
            .join(Assay)
            .where(Assay.dataset_id == run.dataset_id, Measurement.active.is_(True))
            .distinct()
        )
    ]
    candidates = list(
        db.scalars(
            select(PoolCandidate)
            .where(PoolCandidate.pool_id == pool_id)
            .order_by(PoolCandidate.rank)
        )
    )
    qualified: list[PoolCandidate] = []
    for candidate in candidates:
        fingerprint = _rdkit_fingerprint(candidate.compound.canonical_smiles)
        max_similarity = (
            max(DataStructs.BulkTanimotoSimilarity(fingerprint, training_fingerprints))
            if training_fingerprints
            else 0.0
        )
        active_similarity = (
            max(DataStructs.BulkTanimotoSimilarity(fingerprint, active_fingerprints))
            if active_fingerprints
            else 0.0
        )
        base_properties, base_reasons = screen_compound(candidate.compound)
        properties = {
            **base_properties,
            "activity_probability": candidate.properties.get("activity_probability"),
            "max_training_similarity": round(max_similarity, 4),
            "max_active_similarity": round(active_similarity, 4),
            "cytotoxicity_evidence": candidate.properties.get(
                "cytotoxicity_evidence", "not_available"
            ),
        }
        reasons = list(base_reasons)
        if max_similarity >= similarity_threshold and "training_set_similarity" not in reasons:
            reasons.append("training_set_similarity")
        candidate.properties = properties
        candidate.rejection_reasons = reasons
        candidate.passed_screen = not reasons
        if candidate.passed_screen:
            qualified.append(candidate)
    for candidate in candidates:
        candidate.selected = candidate in qualified[:20]
    pool.screening_rules = {
        **pool.screening_rules,
        "max_training_similarity": similarity_threshold,
        "availability_required": True,
        "cytotoxicity_evidence_required": True,
    }
    db.commit()
    db.refresh(pool)
    return pool


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
    selected = [candidate for candidate in candidates if candidate.selected]
    if not 10 <= len(selected) <= 20:
        raise ValueError("Preregistration requires 10 to 20 selected candidates")
    if any(candidate.availability_status != "confirmed" for candidate in selected):
        raise ValueError("Every selected candidate requires confirmed availability")
    if any(
        candidate.properties.get("cytotoxicity_evidence") in {None, "not_available"}
        for candidate in selected
    ):
        raise ValueError("Every selected candidate requires cytotoxicity evidence")
    protocol = db.scalar(select(LaboratoryProtocol).where(LaboratoryProtocol.pool_id == pool_id))
    if protocol is None:
        raise ValueError("A complete laboratory protocol is required")
    report = {
        "schema_version": 1,
        "pool_id": pool.id,
        "pool_sha256": pool.content_sha256,
        "model_run_id": pool.model_run_id,
        "screening_rules": pool.screening_rules,
        "protocol": {
            "sha256": protocol.protocol_sha256,
            "organism": protocol.organism,
            "strain": protocol.strain,
            "method": protocol.method,
            "medium": protocol.medium,
            "concentration_range": [
                protocol.concentration_min,
                protocol.concentration_max,
                protocol.concentration_unit,
            ],
            "replicates": protocol.replicates,
            "positive_control": protocol.positive_control,
            "negative_control": protocol.negative_control,
            "blinded": protocol.blinded,
            "success_criterion": protocol.success_criterion,
            "laboratory": protocol.laboratory,
        },
        "candidates": [
            {
                "compound_id": item.compound_id,
                "rank": item.rank,
                "passed_screen": item.passed_screen,
                "rejection_reasons": item.rejection_reasons,
                "properties": item.properties,
                "availability": {
                    "status": item.availability_status,
                    "vendor": item.vendor,
                    "catalog_number": item.catalog_number,
                    "price": item.price,
                    "purity": item.purity,
                },
            }
            for item in selected
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
