// V001 — Migration tracking infrastructure
// Creates the unique constraint on :Migration nodes used
// by the migration runner itself.

CREATE CONSTRAINT migration_version_unique IF NOT EXISTS
FOR (m:Migration) REQUIRE m.version IS UNIQUE;
