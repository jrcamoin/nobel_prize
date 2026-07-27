from pathlib import Path

from app.artifacts import upload_artifact
from app.config import Settings


def test_artifact_upload_is_optional(tmp_path: Path):
    artifact = tmp_path / "model.joblib"
    artifact.write_bytes(b"model")

    assert upload_artifact(artifact, Settings(s3_endpoint_url="")) is None
