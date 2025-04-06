.PHONY: lint test run build up down clean deps

lint:
	ruff check .
	black .

run:
	uvicorn src.main:app --reload

build:
	docker-compose build

up:
	docker-compose up -d --build

down:
	docker-compose down -v

open_db:
	docker exec -it algo-rumble-service-db-1 psql -U postgres

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +


deps:
	pip install -r requirements.txt

migrate:
	alembic upgrade head