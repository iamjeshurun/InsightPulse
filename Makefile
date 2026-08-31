.PHONY: install test build run observability load-test
install:
	python -m pip install -e '.[test]'
	cd frontend && npm ci
test:
	python -m unittest discover -s tests -v
	cd frontend && npm test
build:
	cd frontend && npm run build
run: build
	insightpulse-api
observability:
	docker compose --profile observability up --build
load-test:
	python scripts/load_test.py --requests 100 --concurrency 10
