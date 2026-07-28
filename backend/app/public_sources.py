from urllib.parse import quote


def public_source_links(inchikey: str) -> list[dict[str, str]]:
    return [
        {
            "source": "PubChem",
            "url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{quote(inchikey)}",
            "kind": "compound record",
        },
        {
            "source": "PubChem BioAssay",
            "url": f"https://pubchem.ncbi.nlm.nih.gov/#query={quote(inchikey)}&tab=assay",
            "kind": "bioassay search",
        },
        {
            "source": "BindingDB",
            "url": f"https://bindingdb.org/rwd/bind/chemsearch/marvin/DisplayStructure.jsp?monomerid={quote(inchikey)}",
            "kind": "target affinity search",
        },
    ]
