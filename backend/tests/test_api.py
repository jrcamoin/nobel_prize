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
