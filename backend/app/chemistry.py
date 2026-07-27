from dataclasses import dataclass

from rdkit import Chem
from rdkit.Chem import Descriptors
from rdkit.Chem.Scaffolds import MurckoScaffold


class InvalidSmilesError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedMolecule:
    canonical_smiles: str
    inchikey: str
    scaffold_smiles: str
    molecular_weight: float


def normalize_smiles(smiles: str) -> NormalizedMolecule:
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise InvalidSmilesError("SMILES could not be parsed by RDKit")

    canonical = Chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True)
    scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=molecule, includeChirality=True)
    return NormalizedMolecule(
        canonical_smiles=canonical,
        inchikey=Chem.MolToInchiKey(molecule),
        scaffold_smiles=scaffold or canonical,
        molecular_weight=round(Descriptors.MolWt(molecule), 4),
    )
