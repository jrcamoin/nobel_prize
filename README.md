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
- Searchable public-evidence timelines across imported assays and source datasets

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
make bootstrap
make api
make web
```

`make bootstrap` makes a fresh installation useful: it downloads and imports
public *A. baumannii* MIC evidence from ChEMBL and CO-ADD, then trains one
reproducible baseline per dataset. It is safe to run again; content hashes
prevent duplicate dataset imports and existing model runs are reused. Use
`python backend/scripts/bootstrap_public_data.py --help` to select one source,
refresh the downloads, or import evidence without training.

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

Download up to 1,000 licensed ChEMBL MIC records manually:

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
   Qualification also records maximum Tanimoto similarity to the training set
   and active compounds, reactive-group alerts, solubility risk, and whether
   cytotoxicity evidence is available.
3. Confirm vendor, catalog number, purity, cost, and cytotoxicity source for
   each selected compound through the candidate evidence endpoint.
4. Store the exact strain, MIC method, medium, concentration range, controls,
   replicates, blinding, laboratory, and success criterion using
   `PUT /api/candidate-pools/{pool_id}/protocol`.
5. Configure the signing secret and call
   `POST /api/candidate-pools/{pool_id}/preregister`.
6. Record laboratory work with `POST /api/experiments`.
7. Queue retraining with `POST /api/jobs/train/{dataset_id}` only after the
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

For a single Docker web service (including Render), use `backend/Dockerfile` with
the repository root as its build context. It builds the frontend and serves it at
`/` from FastAPI; API routes remain under `/api` and health is at `/health`.

## Scientific limitations

Scaffold splits are more demanding than random splits but can still
overestimate prospective virtual-screening performance. Assay heterogeneity,
replicate disagreement, censoring relations, strain differences, and class
imbalance require deeper curation before publishing results. A retrospective
metric is not evidence that a compound works; the next meaningful milestone is
a preregistered prediction evaluated by an independent laboratory.

## Evidence-first mode

### Public explorer

The landing page now supports source-linked compound reports, exact list matching,
evidence comparisons, CSV exports, print-to-PDF, and browser-local watches. Share
`/?compound=INCHIKEY` to open a report directly. Links show current evidence; CSV
exports include the report revision for attribution. Upload a CSV with an
`identifier`, `inchikey`, `smiles`, `name`, or `source_id` column (200 rows / 200 KB).
Matching preserves unmatched and ambiguous inputs instead of inventing matches.

Reports collapse identical same-source assay measurements across dataset snapshots.
Cross-source records are not assumed independent. Structured strain, resistance,
method, medium, and publication identifiers are currently unavailable; original
assay descriptions remain visible and the report calls out these gaps. Mixed
benchmark classifications are not proof of contradictory experiments.

Compound and search watches are stored in the current browser. They check for
changes on page load and every minute while open; no email or push delivery is
configured. Compound watches ignore repeated snapshots with unchanged measurements.
Search watches cover the first 50 search matches, not an exhaustive literature feed.

The Docker Compose stack includes one daily `evidence-worker`, which waits for API
health before importing evidence. For a local deployment, run:

```bash
.venv/bin/python backend/scripts/refresh_evidence.py --interval-hours 24
```

Omit the interval for a one-time scheduled run. Use the same working directory and
database configuration as the API. Run only one worker. Attempts are recorded in
the jobs timeline; interrupted jobs older than 12 hours are marked failed and
retried on a later scheduled pass. Each refresh fetches the latest 1,000 ChEMBL
activity IDs by default (up to 10,000 with `--limit`); this is not complete coverage.
Previously imported snapshots are retained. CO-ADD remains an archival source.

The worker configuration is supplied but must be started on your host. Before
public deployment, configure `API_WRITE_KEY`, HTTPS and the deployed CORS origin.
Public reading, matching and exports require no API key. See
[the public pilot guide](docs/public-pilot.md) for user sessions and release checks.

Use **Sync from ChEMBL** in the Datasets panel to download current published
MIC evidence directly into the app. If write authentication is configured, enter
the API write key in the panel (it is kept only in memory). The app polls job
status and reloads evidence when the import finishes. Each job retains its source
manifest, retrieval time, content hash, and any failure. Identical snapshots are
reused. Sync imports evidence; model retraining remains an explicit separate step.
ChEMBL is a periodically released research database, not a real-time laboratory feed.
The sync uses the existing in-process background job mechanism: keep the API running
until completion; production deployments should use a durable worker before scheduling
unattended refreshes. The default fetch is a bounded 1,000-record sample, not the full database.

The primary application workflow is retrospective and computational. Search by
compound name, source ID, InChIKey, or SMILES, then inspect the source-linked
evidence timeline in the compound drawer. ChEMBL and CO-ADD measurements are
public research evidence; model scores are computational prioritization, not
clinical or laboratory validation. PubChem BioAssay and BindingDB adapters can
be added as additional source-specific imports without changing that boundary.
