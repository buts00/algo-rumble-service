#!/bin/bash

set -e

# Створення бази judge0 якщо не існує
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    SELECT 'CREATE DATABASE judge0'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'judge0')\gexec
EOSQL

# Додаткові налаштування для бази judge0 (приклад)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "judge0" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    -- Додаткові SQL-команди для ініціалізації...
EOSQL