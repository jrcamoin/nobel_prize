.PHONY: api api-test benchmark bootstrap coadd-data data db-up migrate web web-test

api:
	uvicorn app.main:app --app-dir backend --reload

api-test:
	pytest backend/tests

migrate:
	alembic upgrade head

data:
	python backend/scripts/download_chembl.py --limit 1000

coadd-data:
	python backend/scripts/download_coadd.py

benchmark:
	python backend/scripts/run_benchmark.py data/raw/chembl_ab_mic.csv

bootstrap: migrate
	python backend/scripts/bootstrap_public_data.py

coadd-benchmark:
	python backend/scripts/run_benchmark.py data/raw/coadd_complete_r03.zip --format coadd

db-up:
	docker compose up -d db

web:
	cd frontend && npm run dev

web-test:
	cd frontend && npm test
