.PHONY: api api-test web web-test

api:
	uvicorn app.main:app --app-dir backend --reload

api-test:
	pytest backend/tests

web:
	cd frontend && npm run dev

web-test:
	cd frontend && npm test

