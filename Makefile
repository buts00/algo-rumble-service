# Targets
.PHONY: lint test run build up down clean deps

# Лінтер
lint:
	ruff check .
	black --check --diff .

# Запуск локально (без Docker)
run:
	uvicorn backend.src.main:app --reload

# Збірка Docker-образу
build:
	docker-compose build

# Запуск через Docker Compose
up:
	docker-compose up -- build

# Зупинка контейнерів
down:
	docker-compose down

# Очистка кешу та тимчасових файлів
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +

# Встановлення залежностей
deps:
	pip install -r system/requirements.txt

# Міграції БД (якщо буде потрібно)
migrate:
	alembic upgrade head