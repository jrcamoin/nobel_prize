import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import AllChem
from sklearn.calibration import calibration_curve
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sqlalchemy import select
from sqlalchemy.orm import Session

from .chemistry import InvalidSmilesError, normalize_smiles
from .models import Assay, Compound, Dataset, Measurement, ModelRun, Prediction

ACTIVE_MIC_UG_ML = 32.0


def mic_to_ug_ml(value: float, units: str, molecular_weight: float) -> float | None:
    normalized = units.lower().replace("μ", "u").replace("µ", "u").replace(" ", "")
    if normalized in {"ug/ml", "ug.ml-1", "microgram/ml"}:
        return value
    if normalized in {"um", "umol/l", "umol.l-1"}:
        return value * molecular_weight / 1000
    return None


def classify_mic(value: float, relation: str | None) -> bool | None:
    relation = (relation or "=").strip()
    if relation in {"=", "<=", "<"}:
        return value <= ACTIVE_MIC_UG_ML
    if relation in {">", ">="}:
        return False if value >= ACTIVE_MIC_UG_ML else None
    return None


def import_chembl_csv(db: Session, csv_path: Path, manifest_path: Path | None = None) -> Dataset:
    manifest_path = manifest_path or csv_path.with_suffix(".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    existing = db.scalar(select(Dataset).where(Dataset.sha256 == manifest["sha256"]))
    if existing:
        return existing
    dataset = Dataset(
        name=manifest["dataset"],
        version="live-api",
        source_url=manifest["source_url"],
        license=manifest["license"],
        query=manifest["query"],
        sha256=manifest["sha256"],
        record_count=manifest["record_count"],
    )
    db.add(dataset)
    db.flush()
    assays: dict[str, Assay] = {}
    compounds: dict[str, Compound] = {}
    with csv_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            try:
                chemistry = normalize_smiles(row["canonical_smiles"])
                value = float(row["standard_value"])
            except (InvalidSmilesError, TypeError, ValueError):
                continue
            mic = mic_to_ug_ml(value, row["standard_units"], chemistry.molecular_weight)
            active = classify_mic(mic, row["standard_relation"]) if mic is not None else None
            if mic is None or active is None:
                continue
            source_id = row["molecule_chembl_id"]
            compound = compounds.get(chemistry.inchikey)
            if compound is None:
                compound = db.scalar(
                    select(Compound).where(Compound.inchikey == chemistry.inchikey)
                )
            if compound is None:
                compound = Compound(
                    name=source_id,
                    source_id=source_id,
                    smiles=row["canonical_smiles"],
                    **chemistry.__dict__,
                    target_pathogen=row["target_organism"] or "Acinetobacter baumannii",
                    activity_score=None,
                    confidence=None,
                    status="measured",
                    evidence_source=f"ChEMBL:{row['document_chembl_id']}",
                )
                db.add(compound)
                db.flush()
            compounds[chemistry.inchikey] = compound
            assay_id = row["assay_chembl_id"]
            assay = assays.get(assay_id)
            if assay is None:
                assay = Assay(
                    dataset_id=dataset.id,
                    external_id=assay_id,
                    organism=row["target_organism"] or "Acinetobacter baumannii",
                    assay_type=row["assay_type"],
                    description=row["assay_description"],
                )
                db.add(assay)
                db.flush()
                assays[assay_id] = assay
            db.add(
                Measurement(
                    compound_id=compound.id,
                    assay_id=assay.id,
                    standard_type="MIC",
                    relation=row["standard_relation"],
                    value=mic,
                    units="ug/mL",
                    active=active,
                )
            )
    db.commit()
    db.refresh(dataset)
    return dataset


def _fingerprint(smiles: str) -> np.ndarray:
    molecule = Chem.MolFromSmiles(smiles)
    fingerprint = AllChem.GetMorganGenerator(radius=2, fpSize=2048).GetFingerprint(molecule)
    array = np.zeros((2048,), dtype=np.uint8)
    DataStructs.ConvertToNumpyArray(fingerprint, array)
    return array


def _git_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() or None


def _metrics(y_true: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    prob_true, prob_pred = calibration_curve(y_true, probabilities, n_bins=5)
    return {
        "average_precision": round(float(average_precision_score(y_true, probabilities)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, probabilities)), 4),
        "brier_score": round(float(brier_score_loss(y_true, probabilities)), 4),
        "calibration": [
            {"predicted": round(float(predicted), 4), "observed": round(float(observed), 4)}
            for observed, predicted in zip(prob_true, prob_pred, strict=True)
        ],
    }


def train_baseline(db: Session, dataset_id: int, artifact_dir: Path, seed: int = 17) -> ModelRun:
    rows = db.execute(
        select(Compound, Measurement.active)
        .join(Measurement)
        .join(Assay)
        .where(Assay.dataset_id == dataset_id)
    ).all()
    replicates: dict[int, tuple[Compound, list[bool]]] = {}
    for compound, active in rows:
        entry = replicates.setdefault(compound.id, (compound, []))
        entry[1].append(bool(active))
    samples: list[tuple[Compound, bool]] = []
    disputed = 0
    for compound, labels in replicates.values():
        active_count = sum(labels)
        if active_count * 2 == len(labels):
            disputed += 1
            continue
        samples.append((compound, active_count * 2 > len(labels)))
    if len(samples) < 20 or len({label for _, label in samples}) < 2:
        raise ValueError("At least 20 compounds spanning both classes are required")
    x = np.stack([_fingerprint(compound.canonical_smiles) for compound, _ in samples])
    y = np.array([label for _, label in samples], dtype=int)
    groups = np.array([compound.scaffold_smiles for compound, _ in samples])
    outer = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
    train_val_idx, test_idx = next(outer.split(x, y, groups))
    inner = GroupShuffleSplit(n_splits=1, test_size=0.125, random_state=seed + 1)
    train_rel, val_rel = next(
        inner.split(x[train_val_idx], y[train_val_idx], groups[train_val_idx])
    )
    train_idx, val_idx = train_val_idx[train_rel], train_val_idx[val_rel]
    if len(set(y[test_idx])) < 2:
        raise ValueError("Scaffold test split contains one class; increase the dataset size")
    models = {
        "logistic_regression": LogisticRegression(
            class_weight="balanced", C=1.0, max_iter=2000, random_state=seed
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=300, class_weight="balanced", min_samples_leaf=2, random_state=seed
        ),
        "majority_class": DummyClassifier(strategy="prior", random_state=seed),
    }
    comparisons: dict[str, Any] = {}
    for model_name, candidate in models.items():
        candidate.fit(x[train_idx], y[train_idx])
        comparisons[model_name] = _metrics(y[test_idx], candidate.predict_proba(x[test_idx])[:, 1])
    model = models["logistic_regression"]
    holdout_ids = sorted(samples[index][0].inchikey for index in test_idx)
    holdout_sha256 = hashlib.sha256("\n".join(holdout_ids).encode()).hexdigest()
    metrics: dict[str, Any] = {
        **comparisons["logistic_regression"],
        "comparisons": comparisons,
        "counts": {
            "all": len(samples),
            "train": len(train_idx),
            "validation": len(val_idx),
            "test": len(test_idx),
            "active": int(y.sum()),
            "replicate_disputes_excluded": disputed,
        },
        "scaffold_overlap": {
            "train_test": len(set(groups[train_idx]) & set(groups[test_idx])),
            "validation_test": len(set(groups[val_idx]) & set(groups[test_idx])),
        },
        "activity_definition": f"MIC <= {ACTIVE_MIC_UG_ML:g} ug/mL",
        "prospective_holdout": {
            "sha256": holdout_sha256,
            "compound_count": len(holdout_ids),
            "frozen": True,
        },
    }
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact = artifact_dir / f"baseline-dataset-{dataset_id}.joblib"
    joblib.dump(
        {"model": model, "metrics": metrics, "seed": seed, "holdout_inchikeys": holdout_ids},
        artifact,
    )
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    run = ModelRun(
        dataset_id=dataset_id,
        name="Morgan fingerprint logistic baseline",
        algorithm="LogisticRegression(class_weight=balanced)",
        split_strategy="Bemis-Murcko GroupShuffleSplit 70/10/20",
        random_seed=seed,
        parameters={"radius": 2, "fingerprint_bits": 2048, "C": 1.0},
        metrics=metrics,
        artifact_sha256=digest,
        git_commit=_git_commit(),
    )
    db.add(run)
    db.flush()
    all_probabilities = model.predict_proba(x)[:, 1]
    for (compound, _), probability in zip(samples, all_probabilities, strict=True):
        confidence = abs(float(probability) - 0.5) * 2
        db.add(
            Prediction(
                compound_id=compound.id,
                model_run_id=run.id,
                activity_probability=float(probability),
                confidence=confidence,
                uncertainty=1 - confidence,
            )
        )
        compound.activity_score = float(probability)
        compound.confidence = confidence
        compound.status = "retrospective prediction"
    db.commit()
    db.refresh(run)
    return run
