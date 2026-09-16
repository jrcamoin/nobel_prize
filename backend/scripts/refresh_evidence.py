"""Run from a daily scheduler; logs every attempt in the public jobs timeline."""

import argparse
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.database import SessionLocal
from app.main import _run_sync_job
from app.models import Job


def refresh(limit: int):
    with SessionLocal() as db:
        active = db.scalars(
            select(Job).where(Job.job_type == "sync_chembl", Job.status.in_(["running", "queued"]))
        ).all()
        for job in active:
            if job.created_at > datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=12):
                print(f"Sync {job.id} is already active; skipping")
                return
            job.status = "failed"
            job.error = (
                "Sync exceeded 12 hours or its process was interrupted; scheduled retry follows."
            )
            job.finished_at = datetime.now(UTC).replace(tzinfo=None)
        job = Job(job_type="sync_chembl", status="queued", parameters={"limit": limit})
        db.add(job)
        db.commit()
        job_id = job.id
    _run_sync_job(job_id, limit)
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        print(f"Sync {job_id}: {job.status}")
        if job.status != "completed":
            raise SystemExit(job.error)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--interval-hours", type=float, default=0)
    args = parser.parse_args()
    if not 1 <= args.limit <= 10000 or args.interval_hours < 0:
        parser.error("limit must be 1–10000; interval must be nonnegative")
    while True:
        try:
            refresh(args.limit)
        except SystemExit:
            if not args.interval_hours:
                raise
            print("Refresh failed; retrying at the next scheduled interval", flush=True)
        if not args.interval_hours:
            break
        time.sleep(args.interval_hours * 3600)


if __name__ == "__main__":
    main()
