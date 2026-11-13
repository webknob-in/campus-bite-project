-- Runs once, on first initialisation of the Postgres data volume (docker-entrypoint-initdb.d).
-- Creates the database used by the pytest suite (TEST_DATABASE_URL).
CREATE DATABASE campusbite_test;
