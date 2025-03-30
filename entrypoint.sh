#!/bin/bash

# Wait for PostgreSQL to be ready
until PGPASSWORD=$DB_PASSWORD psql -h "db" -U "postgres" -d "rememberingDB" -c '\q'; do
  >&2 echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done

>&2 echo "PostgreSQL is up - executing command"

# Execute the command passed to docker run
exec "$@"