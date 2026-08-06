"""Download and import the public datasets needed for a useful first run."""

import argparse
from pathlib import Path

from sqlalchemy import select

from app.benchmark import import_chembl_csv, import_coadd_archive, train_baseline
from app.database import SessionLocal
from app.datasets import download_chembl_mic, download_coadd
from app.models import ModelRun


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate the application with public A. baumannii assay data."
    )
    parser.add_argument(
        "--source", choices=("chembl", "coadd", "all"), default="all"
    )
    parser.add_argument("--limit", type=int, default=1000, help="ChEMBL record limit")
    parser.add_argument(
        "--refresh", action="store_true", help="download source archives again"
    )
    parser.add_argument(
        "--skip-training", action="store_true", help="import evidence without fitting models"
    )
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    args = parser.parse_args()

    raw_dir = Path("data/raw")
    chembl_path = raw_dir / "chembl_ab_mic.csv"
    coadd_path = raw_dir / "coadd_complete_r03.zip"
    selected = ("chembl", "coadd") if args.source == "all" else (args.source,)

    if "chembl" in selected and (
        args.refresh
        or not chembl_path.exists()
        or not chembl_path.with_suffix(".manifest.json").exists()
    ):
        print("Downloading ChEMBL MIC records...")
        download_chembl_mic(chembl_path, args.limit)
    if "coadd" in selected and (args.refresh or not coadd_path.exists()):
        print("Downloading the CO-ADD public screening archive...")
        download_coadd(coadd_path)

    with SessionLocal() as db:
        datasets = []
        if "chembl" in selected:
            datasets.append(import_chembl_csv(db, chembl_path))
        if "coadd" in selected:
            datasets.append(import_coadd_archive(db, coadd_path))

        for dataset in datasets:
            run = db.scalar(select(ModelRun).where(ModelRun.dataset_id == dataset.id).limit(1))
            if not args.skip_training and run is None:
                print(f"Training reproducible baseline for {dataset.name}...")
                run = train_baseline(db, dataset.id, args.artifacts)
            run_label = f", model run {run.id}" if run else ""
            print(
                f"Ready: {dataset.name} ({dataset.record_count} evidence records{run_label})"
            )


if __name__ == "__main__":
    main()
