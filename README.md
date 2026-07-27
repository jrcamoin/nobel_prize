# Open Antibiotic Discovery

A reproducible research workspace for ranking antimicrobial compounds with
traceable measurements, model runs, and uncertainty. It is not a validated
drug-discovery system and must not be used for clinical decisions.

## What is implemented

- RDKit SMILES validation, canonicalization, InChIKey, molecular weight, and Murcko scaffold
- ChEMBL MIC downloader for *Acinetobacter baumannii*
- Dataset manifests containing the exact query, source URL, license, record count, and SHA-256
- Assay, measurement, model-run, prediction, and experiment provenance
- Morgan fingerprint logistic-regression baseline with scaffold-group splitting
- Average precision, ROC AUC, Brier score, calibration bins, class counts, and overlap checks
- Alembic migrations, PostgreSQL/SQLite support, containers, API tests, UI tests, and CI

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e "./backend[dev]"
npm install --prefix frontend
alembic upgrade head
```

Run the services in separate terminals:

```bash
make api
make web
```

API documentation is at `http://localhost:8000/docs`; the application is at
`http://localhost:5173`.

## Reproducible benchmark

Download a bounded, licensed ChEMBL dataset:

```bash
make data
```

This writes `data/raw/chembl_ab_mic.csv` and a manifest beside it. Raw data is
ignored by Git because it is reproducibly fetched and content-addressed.
ChEMBL is distributed under CC BY-SA 3.0; cite the current ChEMBL publication
when publishing derived work.

Import, scaffold-split, train, evaluate, and record the run:

```bash
make benchmark
```

MIC values in `ug/mL` and `uM` are normalized to `ug/mL`; other units are
excluded. The initial activity definition is `MIC <= 32 ug/mL`. This is an
explicit benchmark convention, not a universal biological breakpoint.

## Commands

```bash
make migrate   # apply database migrations
make api-test  # backend tests
make web-test  # frontend tests
docker compose up --build  # PostgreSQL + API + production web at :8080
```

## Scientific limitations

Scaffold splits are more demanding than random splits but can still
overestimate prospective virtual-screening performance. Assay heterogeneity,
replicate disagreement, censoring relations, strain differences, and class
imbalance require deeper curation before publishing results. A retrospective
metric is not evidence that a compound works; the next meaningful milestone is
a preregistered prediction evaluated by an independent laboratory.
