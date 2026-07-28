def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_and_rank_compounds(client):
    response = client.post(
        "/api/compounds",
        json={
            "name": "Candidate B",
            "smiles": "CCO",
            "target_pathogen": "Acinetobacter baumannii",
            "evidence_source": "Unit test fixture",
        },
    )

    assert response.status_code == 201
    compound = response.json()
    assert compound["canonical_smiles"] == "CCO"
    assert compound["inchikey"] == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"


def test_rejects_invalid_smiles(client):
    response = client.post(
        "/api/compounds",
        json={
            "name": "Invalid",
            "smiles": "not-a-molecule",
            "target_pathogen": "Acinetobacter baumannii",
            "evidence_source": "Unit test fixture",
        },
    )

    assert response.status_code == 422


def test_missing_compound_detail_returns_404(client):
    assert client.get("/api/compounds/999").status_code == 404


def test_missing_model_report_returns_404(client):
    assert client.get("/api/model-runs/999/report").status_code == 404


def test_training_job_requires_dataset(client):
    assert client.post("/api/jobs/train/999").status_code == 404


def test_qualification_requires_pool(client):
    assert client.post("/api/candidate-pools/999/qualify").status_code == 422


def test_search_requires_query(client):
    assert client.get("/api/search?query=CCO").status_code == 200
