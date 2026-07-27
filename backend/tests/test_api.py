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
            "activity_score": 0.91,
            "confidence": 0.74,
            "status": "predicted",
            "evidence_source": "Unit test fixture",
        },
    )

    assert response.status_code == 201
    compounds = client.get("/api/compounds").json()
    assert compounds[0]["name"] == "Candidate B"
