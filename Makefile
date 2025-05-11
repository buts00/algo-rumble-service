.PHONY: lint test test-auth test-match test-cov run build up down clean deps nuke migrate migrate-create

lint:
	ruff check .
	black .

test:
	pytest -v

test-auth:
	pytest -v tests/auth

test-match:
	pytest -v tests/match

test-cov:
	pytest --cov=src --cov-report=term --cov-report=html

run:
	uvicorn src.main:app --reload --port 8001

build:
	docker-compose build

up:
	docker-compose up -d --build

down:
	docker-compose down -v

nuke:
	docker-compose down --remove-orphans

open_db:
	docker exec -it algo-rumble-service-db-1 psql -U postgres

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} +

deps:
	pip install -r requirements.txt

migrate:
	alembic upgrade head

migrate-create:
	alembic revision --autogenerate -m "$(message)"

format:
	black .
	isort .
