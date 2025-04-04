.PHONY: lint test run build up down clean deps

lint:
	ruff check .
	black --check --diff .

run:
	uvicorn src.main:app --reload

build:
	docker-compose build

up:
	docker-compose up -d --build
down:
	docker-compose down -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +

deps:
	pip install -r system/requirements.txt

migrate:
	alembic upgrade head