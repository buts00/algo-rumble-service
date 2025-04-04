#!/bin/bash
set -e

echo "Initializing PostgreSQL databases..."

# Підключаємось під головним користувачем
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<EOSQL
    -- Створення бази даних, якщо її ще немає
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_database WHERE datname = '$POSTGRES_DB') THEN
            CREATE DATABASE $POSTGRES_DB;
        END IF;
    END
    \$\$;

    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'judge0') THEN
            CREATE DATABASE judge0;
        END IF;
    END
    \$\$;
EOSQL

# Створення або оновлення користувачів
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$POSTGRES_USER') THEN
            CREATE USER $POSTGRES_USER WITH ENCRYPTED PASSWORD '$POSTGRES_PASSWORD';
        ELSE
            ALTER ROLE $POSTGRES_USER WITH ENCRYPTED PASSWORD '$POSTGRES_PASSWORD';
        END IF;
    END
    \$\$;

    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'judge0') THEN
            CREATE USER judge0 WITH ENCRYPTED PASSWORD 'judge0password';
        ELSE
            ALTER ROLE judge0 WITH ENCRYPTED PASSWORD 'judge0password';
        END IF;
    END
    \$\$;

    -- Видаємо права
    GRANT ALL PRIVILEGES ON DATABASE $POSTGRES_DB TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON DATABASE judge0 TO judge0;
EOSQL

echo "PostgreSQL databases initialized successfully."
