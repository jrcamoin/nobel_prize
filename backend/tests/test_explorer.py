from app.database import SessionLocal
from app.models import Assay, Compound, Dataset, Measurement


def seed():
    with SessionLocal() as db:
        compound = Compound(
            name="Example",
            source_id="CHEMBL1",
            smiles="CCO",
            canonical_smiles="CCO",
            inchikey="LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
            scaffold_smiles="",
            molecular_weight=46,
            target_pathogen="Acinetobacter baumannii",
            evidence_source="test",
        )
        db.add(compound)
        db.flush()
        for i in range(2):
            dataset = Dataset(
                name="ChEMBL test",
                version=str(i),
                source_url="https://example.org",
                license="CC BY-SA 3.0",
                sha256=str(i) * 64,
                record_count=1,
            )
            db.add(dataset)
            db.flush()
            assay = Assay(dataset_id=dataset.id, external_id="CHEMBL2", organism="A. baumannii")
            db.add(assay)
            db.flush()
            db.add(
                Measurement(
                    compound_id=compound.id,
                    assay_id=assay.id,
                    standard_type="MIC",
                    relation="=",
                    value=8,
                    units="ug/mL",
                    active=True,
                )
            )
        db.commit()
        return compound.inchikey


def test_report_collapses_snapshots_and_exports_citations(client):
    key = seed()
    response = client.get(f"/api/explorer/reports/{key}")
    assert response.status_code == 200
    data = response.json()
    assert data["unique_record_count"] == 1
    assert data["repeated_snapshot_records"] == 1
    assert data["evidence"][0]["strain"] is None
    assert data["gaps"]
    exported = client.get(f"/api/explorer/reports/{key}/export")
    assert "CHEMBL2" in exported.text
    assert data["revision"] in exported.text


def test_matching_preserves_missing_and_quotes_formulas(client):
    seed()
    data = client.post("/api/explorer/match", json={"csv": "identifier\nCHEMBL1\nmissing\n"}).json()
    assert [r["status"] for r in data["results"]] == ["matched", "unmatched"]
    response = client.post("/api/explorer/match/export", json={"csv": "name\n=1+1\n"})
    assert "'=1+1" in response.text
    assert client.post("/api/explorer/match", json={"csv": "other\nx"}).status_code == 422


def test_reports_are_public_and_unknown_compounds_are_404(client):
    assert client.get("/api/explorer/reports/unknown").status_code == 404
    assert client.get("/api/explorer/compare?keys=one").status_code == 422


def test_cross_source_matches_are_flagged_not_merged(client):
    key = seed()
    before = client.get(f"/api/explorer/reports/{key}").json()
    with SessionLocal() as db:
        dataset = Dataset(
            name="CO-ADD",
            version="r03",
            source_url="https://example.org",
            license="test",
            sha256="c" * 64,
            record_count=2,
        )
        db.add(dataset)
        db.flush()
        assay = Assay(dataset_id=dataset.id, external_id="COADD1", organism="A. baumannii")
        db.add(assay)
        db.flush()
        for value in [8, 128]:
            db.add(
                Measurement(
                    compound_id=1,
                    assay_id=assay.id,
                    standard_type="MIC",
                    relation="=",
                    value=value,
                    units="ug/mL",
                    active=value <= 32,
                )
            )
        db.commit()
    data = client.get(f"/api/explorer/reports/{key}").json()
    assert data["unique_record_count"] == 3
    assert data["possible_cross_source_overlaps"] == 1
    assert data["mixed_outcomes"] is True
    assert data["evidence_revision"] != before["evidence_revision"]


def test_csv_limits_and_bom(client):
    seed()
    assert (
        client.post("/api/explorer/match", json={"csv": "\ufeffidentifier\nCHEMBL1"}).json()[
            "results"
        ][0]["status"]
        == "matched"
    )
    assert client.post("/api/explorer/match", json={"csv": "identifier\n"}).status_code == 422
    assert (
        client.post("/api/explorer/match", json={"csv": "name\n" + "unknown\n" * 201}).status_code
        == 422
    )
