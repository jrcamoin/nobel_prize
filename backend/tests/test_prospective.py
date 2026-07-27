from app.chemistry import normalize_smiles
from app.models import Compound
from app.prospective import screen_compound


def test_screen_compound_records_properties():
    chemistry = normalize_smiles("CCO")
    compound = Compound(
        name="ethanol",
        source_id=None,
        smiles="CCO",
        **chemistry.__dict__,
        target_pathogen="Acinetobacter baumannii",
        activity_score=None,
        confidence=None,
        status="unscored",
        evidence_source="test",
    )

    properties, reasons = screen_compound(compound)

    assert properties["molecular_weight"] < 50
    assert properties["pains_alert"] is None
    assert reasons == []
