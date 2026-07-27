import csv
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"
CHEMBL_LICENSE = "CC BY-SA 3.0"


def _json(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=30) as response:
        return json.load(response)


def download_chembl_mic(output: Path, limit: int = 1000) -> Path:
    query = {
        "target_organism": "Acinetobacter baumannii",
        "standard_type": "MIC",
        "limit": min(limit, 1000),
    }
    url = f"{CHEMBL_API}/activity.json?{urlencode(query)}"
    payload = _json(url)
    activities = payload.get("activities", [])[:limit]
    molecule_cache: dict[str, str | None] = {}
    rows: list[dict[str, Any]] = []
    for activity in activities:
        molecule_id = activity.get("molecule_chembl_id")
        if not molecule_id:
            continue
        if molecule_id not in molecule_cache:
            molecule = _json(f"{CHEMBL_API}/molecule/{molecule_id}.json")
            molecule_cache[molecule_id] = (molecule.get("molecule_structures") or {}).get(
                "canonical_smiles"
            )
        smiles = molecule_cache[molecule_id]
        if not smiles:
            continue
        rows.append(
            {
                "molecule_chembl_id": molecule_id,
                "canonical_smiles": smiles,
                "assay_chembl_id": activity.get("assay_chembl_id"),
                "assay_description": activity.get("assay_description"),
                "assay_type": activity.get("assay_type"),
                "target_organism": activity.get("target_organism"),
                "standard_type": activity.get("standard_type"),
                "standard_relation": activity.get("standard_relation"),
                "standard_value": activity.get("standard_value"),
                "standard_units": activity.get("standard_units"),
                "document_chembl_id": activity.get("document_chembl_id"),
            }
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".manifest.json").write_text(
        json.dumps(
            {
                "dataset": "ChEMBL Acinetobacter baumannii MIC",
                "source_url": url,
                "license": CHEMBL_LICENSE,
                "query": query,
                "sha256": digest,
                "record_count": len(rows),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return output
