import pytest

from app import datasets, main


def test_sync_imports_real_format_and_reuses_snapshot(client, monkeypatch):
    def source(url):
        if "/molecule/" in url:
            return {"molecule_structures": {"canonical_smiles": "CCO"}}
        return {"activities": [{
            "molecule_chembl_id": "CHEMBL1", "assay_chembl_id": "CHEMBL2",
            "assay_description": "MIC assay", "assay_type": "F",
            "target_organism": "Acinetobacter baumannii", "standard_type": "MIC",
            "standard_relation": "=", "standard_value": "8",
            "standard_units": "ug/mL", "document_chembl_id": "CHEMBL3",
        }], "page_meta": {"next": None}}

    monkeypatch.setattr(datasets, "_json", source)
    for _ in range(2):
        assert client.post("/api/jobs/sync/chembl?limit=1").status_code == 202
    jobs = client.get("/api/jobs").json()
    assert all(job["status"] == "completed" for job in jobs)
    assert jobs[0]["result"]["manifest"]["retrieved_at"]
    assert len(client.get("/api/datasets").json()) == 1
    assert len(client.get("/api/compounds").json()) == 1


def test_sync_failure_is_visible(client, monkeypatch):
    def fail(*args):
        raise TimeoutError("Source timed out")

    monkeypatch.setattr(main, "download_chembl_mic", fail)
    response = client.post("/api/jobs/sync/chembl?limit=10")
    assert response.status_code == 202
    job = client.get("/api/jobs").json()[0]
    assert job["status"] == "failed"
    assert job["error"] == "Source timed out"


def test_sync_requires_write_key(client, monkeypatch):
    monkeypatch.setattr(main.settings, "api_write_key", "test-secret")
    assert client.post("/api/jobs/sync/chembl").status_code == 401


def test_sync_limit_validation(client):
    assert client.post("/api/jobs/sync/chembl?limit=10001").status_code == 422


def test_downloader_paginates_and_records_retrieval(tmp_path, monkeypatch):
    calls = []

    def fake_json(url):
        calls.append(url)
        if "/molecule/" in url:
            return {"molecule_structures": {"canonical_smiles": "CCO"}}
        return {"activities": [{"molecule_chembl_id": "CHEMBL1"}],
                "page_meta": {"next": "next" if "offset=0" in url else None}}

    monkeypatch.setattr(datasets, "_json", fake_json)
    output = datasets.download_chembl_mic(tmp_path / "data.csv", 2)
    assert len(output.read_text().splitlines()) == 3
    assert any("offset=1" in url for url in calls)
    assert "retrieved_at" in output.with_suffix(".manifest.json").read_text()


def test_empty_source_does_not_replace_file(tmp_path, monkeypatch):
    monkeypatch.setattr(datasets, "_json", lambda _: {"activities": []})
    output = tmp_path / "data.csv"
    output.write_text("existing evidence")
    with pytest.raises(ValueError, match="no MIC records"):
        datasets.download_chembl_mic(output)
    assert output.read_text() == "existing evidence"
