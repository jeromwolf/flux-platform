#!/bin/bash
set -e

# Create the imsp database for IMSP platform data.
# Runs as part of docker-entrypoint-initdb.d. Creates the imsp database if it does not exist.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    SELECT 'CREATE DATABASE imsp'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'imsp')\gexec
EOSQL
