import argparse
from pathlib import Path

from app.benchmark import import_chembl_csv, train_baseline
from app.database import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    with SessionLocal() as db:
        dataset = import_chembl_csv(db, args.csv)
        run = train_baseline(db, dataset.id, args.artifacts, args.seed)
        print(f"model_run={run.id} metrics={run.metrics}")


if __name__ == "__main__":
    main()
