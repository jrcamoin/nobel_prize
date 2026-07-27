# Open Antibiotic Discovery

A reproducible research workspace for ranking antimicrobial compounds with
traceable measurements, model runs, and uncertainty. It is not a validated
drug-discovery system and must not be used for clinical decisions.

## What is implemented

- RDKit SMILES validation, canonicalization, InChIKey, molecular weight, and Murcko scaffold
- ChEMBL MIC downloader for *Acinetobacter baumannii*
- Dataset manifests containing the exact query, source URL, license, record count, and SHA-256
- Official CO-ADD dose-response archive ingestion for *A. baumannii*
- Assay, measurement, model-run, prediction, and experiment provenance
- Morgan fingerprint logistic-regression and random-forest baselines with a majority-class control
- Average precision, ROC AUC, Brier score, calibration bins, class counts, and overlap checks
- Alembic migrations, PostgreSQL/SQLite support, containers, API tests, UI tests, and CI
- Immutable candidate pools, PAINS/property screening, signed preregistration, experiments, and jobs

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

Set `API_WRITE_KEY` to require an `X-API-Key` header for mutation endpoints.
Read-only scientific evidence remains accessible for review and reproducibility.
Model evidence packages can be exported from
`GET /api/model-runs/{run_id}/report`.

Set `PREREGISTRATION_SIGNING_KEY` to a high-entropy secret before locking a
candidate pool. The canonical report is SHA-256 hashed and HMAC-SHA256 signed.
The signing key must be retained outside the database to verify the commitment.

## Reproducible benchmark

Download up to 1,000 licensed ChEMBL MIC records:

```bash
make data
make coadd-data
```

This writes `data/raw/chembl_ab_mic.csv` and a manifest beside it. Raw data is
ignored by Git because it is reproducibly fetched and content-addressed.
ChEMBL is distributed under CC BY-SA 3.0; cite the current ChEMBL publication
when publishing derived work.

`make coadd-data` downloads the official CO-ADD r03 complete CSV archive. Run
`make coadd-benchmark` to import its *A. baumannii* dose-response MIC records
and apply the same scaffold-held-out benchmark.

The container stack includes MinIO for S3-compatible model artifact storage.
Background training uploads artifacts when `S3_ENDPOINT_URL` is configured;
local CLI runs continue to retain content-addressed files under `artifacts/`.

Import, scaffold-split, train, evaluate, and record the run:

```bash
make benchmark
```

MIC values in `ug/mL` and `uM` are normalized to `ug/mL`; other units are
excluded. Censored relations are interpreted conservatively; ambiguous
measurements are excluded. The initial activity definition is `MIC <= 32 ug/mL`. This is an
explicit benchmark convention, not a universal biological breakpoint.

Every run evaluates all baseline models on the same scaffold-held-out compounds.
The sorted holdout InChIKeys are SHA-256 hashed and stored in the model artifact
and metrics, allowing a prospective evaluation set to be frozen before testing.

## Prospective workflow

1. Create a candidate pool with `POST /api/candidate-pools`.
2. Review recorded property bounds, PAINS alerts, ranks, and rejections.
3. Configure the signing secret and call
   `POST /api/candidate-pools/{pool_id}/preregister`.
4. Record laboratory work with `POST /api/experiments`.
5. Queue retraining with `POST /api/jobs/train/{dataset_id}` only after the
   prospective results are locked.

Preregistered pools cannot be edited through the API. A new hypothesis requires
a new pool and a new signed report.

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
