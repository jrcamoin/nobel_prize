"""Public, read-only evidence reports and list matching."""

import csv
import hashlib
import io
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .chemistry import InvalidSmilesError, normalize_smiles
from .database import get_db
from .models import Assay, Compound, Dataset, Measurement, Prediction

router = APIRouter(prefix="/api/explorer", tags=["public explorer"])
Database = Annotated[Session, Depends(get_db)]


def report(db: Session, compound: Compound) -> dict:
    rows = db.execute(
        select(Measurement, Assay, Dataset)
        .join(Assay, Measurement.assay_id == Assay.id)
        .join(Dataset, Assay.dataset_id == Dataset.id)
        .where(Measurement.compound_id == compound.id)
        .order_by(Dataset.imported_at, Measurement.id)
    ).all()
    evidence = {}
    for measurement, assay, dataset in rows:
        family = "ChEMBL" if dataset.name.startswith("ChEMBL") else dataset.name
        key = (
            family,
            assay.external_id,
            assay.organism,
            measurement.standard_type,
            measurement.relation,
            measurement.value,
            measurement.units,
        )
        if key in evidence:
            evidence[key]["snapshot_count"] += 1
            continue
        evidence[key] = {
            "assay_id": assay.external_id,
            "organism": assay.organism,
            "description": assay.description,
            "assay_type": assay.assay_type,
            "strain": None,
            "method": None,
            "medium": None,
            "publication": None,
            "value": measurement.value,
            "relation": measurement.relation,
            "units": measurement.units,
            "endpoint": measurement.standard_type,
            "active": measurement.active,
            "source": family,
            "license": dataset.license,
            "source_url": dataset.source_url,
            "assay_url": (
                f"https://www.ebi.ac.uk/chembl/explore/assay/{assay.external_id}"
                if family == "ChEMBL"
                else dataset.source_url
            ),
            "dataset_sha256": dataset.sha256,
            "imported_at": dataset.imported_at.isoformat(),
            "snapshot_count": 1,
        }
    items = list(evidence.values())
    overlaps = {}
    for item in items:
        signature = (
            item["organism"],
            item["endpoint"],
            item["relation"],
            item["value"],
            item["units"],
        )
        overlaps.setdefault(signature, set()).add(item["source"])
    possible_overlaps = sum(len(sources) > 1 for sources in overlaps.values())
    outcomes = {item["active"] for item in items}
    gaps = [
        "Strain, resistance phenotype, method, medium and publication identifiers are not structured in the imported records; inspect the linked assay descriptions.",
        "Cytotoxicity and independent laboratory confirmation are not established by this report.",
    ]
    if not items:
        gaps.insert(
            0,
            "No usable measurements in the imported datasets. This does not establish inactivity.",
        )
    predictions = db.scalars(select(Prediction).where(Prediction.compound_id == compound.id)).all()
    content = {
        "compound": {
            "id": compound.id,
            "name": compound.name,
            "inchikey": compound.inchikey,
            "smiles": compound.canonical_smiles,
            "molecular_weight": compound.molecular_weight,
        },
        "evidence": items,
        "raw_record_count": len(rows),
        "unique_record_count": len(items),
        "repeated_snapshot_records": len(rows) - len(items),
        "possible_cross_source_overlaps": possible_overlaps,
        "mixed_outcomes": len(outcomes) > 1,
        "interpretation": (
            "Measurements fall on both sides of the benchmark threshold; different assay conditions may explain this."
            if len(outcomes) > 1
            else "No mixed benchmark classifications found in the available records."
        ),
        "comparison_note": "MIC <= 32 ug/mL is the app's research benchmark, not a clinical breakpoint. Different strains and methods cannot be assumed comparable. Cross-source independence is unverified; counts are records, not independent studies.",
        "gaps": gaps,
        "predictions": [
            {
                "model_run_id": p.model_run_id,
                "probability": p.activity_probability,
                "uncertainty": p.uncertainty,
            }
            for p in predictions
        ],
    }
    content["revision"] = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
    # Changes to the observed evidence, rather than repeated source snapshots, trigger alerts.
    content["evidence_revision"] = hashlib.sha256(
        json.dumps(sorted(str(key) for key in evidence), sort_keys=True).encode()
    ).hexdigest()
    return content


@router.get("/reports/{inchikey}")
def get_report(inchikey: str, db: Database) -> dict:
    compound = db.scalar(select(Compound).where(Compound.inchikey == inchikey))
    if compound is None:
        raise HTTPException(404, "Compound not found")
    return report(db, compound)


def csv_response(rows: list[dict], filename: str) -> Response:
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            # Spreadsheet applications must not execute uploaded cells as formulas.
            writer.writerow(
                {
                    key: (
                        "'" + value
                        if isinstance(value, str)
                        and value.startswith(("=", "+", "-", "@", "\t", "\r"))
                        else value
                    )
                    for key, value in row.items()
                }
            )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/{inchikey}/export")
def export_report(inchikey: str, db: Database):
    data = get_report(inchikey, db)
    return csv_response(
        [
            {"inchikey": inchikey, "report_revision": data["revision"], **item}
            for item in data["evidence"]
        ],
        f"evidence-{inchikey}.csv",
    )


class ListRequest(BaseModel):
    csv: str = Field(min_length=1, max_length=200000)


def match_list(payload: ListRequest, db: Session) -> list[dict]:
    try:
        reader = csv.DictReader(io.StringIO(payload.csv.lstrip("\ufeff")), strict=True)
        columns = reader.fieldnames or []
        field = next(
            (
                c
                for c in columns
                if c.lower().strip() in {"identifier", "inchikey", "smiles", "name", "source_id"}
            ),
            None,
        )
        if field is None:
            raise HTTPException(
                422, "CSV needs an identifier, inchikey, smiles, name or source_id column"
            )
        results = []
        for index, row in enumerate(reader):
            if index >= 200:
                raise HTTPException(422, "Upload at most 200 compounds per list")
            value = (row.get(field) or "").strip()
            candidates = (
                list(
                    db.scalars(
                        select(Compound).where(
                            or_(
                                func.lower(Compound.name) == value.lower(),
                                Compound.source_id == value,
                                Compound.inchikey == value.upper(),
                                Compound.canonical_smiles == value,
                            )
                        )
                    ).all()
                )
                if value
                else []
            )
            if not candidates and value and field.lower().strip() in {"identifier", "smiles"}:
                try:
                    key = normalize_smiles(value).inchikey
                    candidates = list(db.scalars(select(Compound).where(Compound.inchikey == key)))
                except InvalidSmilesError:
                    pass
            item = {
                "input": value,
                "status": "matched"
                if len(candidates) == 1
                else "ambiguous"
                if candidates
                else "unmatched",
                "inchikey": "",
                "name": "",
                "records": 0,
                "mixed_outcomes": False,
                "sources": "",
                "gaps": "",
            }
            if len(candidates) == 1:
                data = report(db, candidates[0])
                item.update(
                    inchikey=candidates[0].inchikey,
                    name=candidates[0].name,
                    records=data["unique_record_count"],
                    mixed_outcomes=data["mixed_outcomes"],
                    sources=" | ".join(sorted({e["assay_url"] for e in data["evidence"]})),
                    gaps=" | ".join(data["gaps"]),
                )
            results.append(item)
        if not results:
            raise HTTPException(422, "CSV needs at least one compound row")
        return results
    except csv.Error as exc:
        raise HTTPException(422, "Malformed CSV") from exc


@router.post("/match")
def match(payload: ListRequest, db: Database) -> dict:
    return {"results": match_list(payload, db)}


@router.post("/match/export")
def export_matches(payload: ListRequest, db: Database):
    return csv_response(match_list(payload, db), "compound-evidence-matches.csv")


@router.get("/compare")
def compare(db: Database, keys: Annotated[str, Query(max_length=300)]) -> dict:
    identifiers = list(dict.fromkeys(keys.split(",")))
    if not 2 <= len(identifiers) <= 8:
        raise HTTPException(422, "Select between two and eight compounds")
    return {
        "reports": [get_report(key, db) for key in identifiers],
        "note": "These summaries do not establish relative potency. Compare original assay conditions before interpreting differences.",
    }
