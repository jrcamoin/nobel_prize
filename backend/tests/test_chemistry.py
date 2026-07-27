import pytest

from app.benchmark import mic_to_ug_ml
from app.chemistry import InvalidSmilesError, normalize_smiles


def test_normalizes_smiles_and_scaffold():
    molecule = normalize_smiles("C(C)O")

    assert molecule.canonical_smiles == "CCO"
    assert molecule.molecular_weight == pytest.approx(46.069, abs=0.001)


def test_invalid_smiles_raises():
    with pytest.raises(InvalidSmilesError):
        normalize_smiles("not-a-molecule")


def test_mic_unit_conversion():
    assert mic_to_ug_ml(10, "ug/mL", 200) == 10
    assert mic_to_ug_ml(50, "uM", 200) == 10
    assert mic_to_ug_ml(10, "nM", 200) is None
