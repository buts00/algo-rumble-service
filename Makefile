.PHONY: lint test run build up down clean deps

# Лінтер
lint:
	ruff check .
	black --check --diff .

# Запуск локально (без Docker)
run:
	uvicorn src.main:app --reload

# Збірка Docker-образу
build:
	docker-compose build

# Запуск через Docker Compose
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
	pip install -r system/requirements.txt

migrate:
	alembic upgrade head