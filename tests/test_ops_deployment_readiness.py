"""Deployment readiness must follow the database, without mutating it."""
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from fastapi.testclient import TestClient

from nurion_pg.api.app import create_app
from nurion_pg.api.settings import Settings
from nurion_pg.storage.postgres import PostgresFoundation, _checksum


class ReadinessTests(unittest.TestCase):
    def test_image_contains_separate_migration_command(self):
        root = Path(__file__).resolve().parents[1]
        self.assertIn("COPY scripts/migrate_ops_database.py", (root / "Dockerfile").read_text())

    def test_lifespan_rejects_schema_drift_without_migrating(self):
        connection = MagicMock(autocommit=True)
        app = create_app(Settings(environment="production", database_url="postgresql://db/test"))
        with patch("psycopg.connect", return_value=connection), patch(
            "nurion_pg.storage.postgres.PostgresFoundation.is_current", return_value=False
        ), patch("nurion_pg.storage.postgres.PostgresFoundation.migrate_up") as migrate:
            with self.assertRaisesRegex(RuntimeError, "migration preflight failed"):
                with TestClient(app):
                    pass
            migrate.assert_not_called()
        connection.close.assert_called_once()

    def test_lifespan_ready_then_fails_on_database_error(self):
        connection = MagicMock(autocommit=True)
        app = create_app(Settings(environment="production", database_url="postgresql://db/test"))
        with patch("psycopg.connect", return_value=connection), patch(
            "nurion_pg.storage.postgres.PostgresFoundation.is_current", side_effect=[True, True, False]
        ), patch("nurion_pg.storage.postgres.PostgresFoundation.migrate_up") as migrate:
            with TestClient(app) as client:
                self.assertEqual(client.get("/health/ready").status_code, 200)
                self.assertEqual(client.get("/health/ready").status_code, 503)
            migrate.assert_not_called()
        connection.close.assert_called_once()

    def test_runtime_loses_readiness_when_migration_check_fails(self):
        app = create_app(Settings(environment="production", database_url="postgresql://db/test"))

        class Foundation:
            current = True

            def is_current(self):
                return self.current

        foundation = Foundation()
        app.state.db_foundation = foundation
        client = TestClient(app)
        self.assertEqual(client.get("/health/ready").status_code, 200)
        foundation.current = False
        self.assertEqual(client.get("/health/ready").status_code, 503)
        self.assertEqual(client.get("/health/live").status_code, 200)

    def test_migration_check_is_read_only_and_fails_closed(self):
        class Connection:
            autocommit = True

            def __init__(self):
                self.rows = [(n, _checksum(n)) for n in range(1, 8)]
                self.queries = []

            def execute(self, sql):
                self.queries.append(sql)
                return self

            def fetchall(self):
                return self.rows

        connection = Connection()
        foundation = PostgresFoundation(connection)
        self.assertTrue(foundation.is_current())
        connection.rows[-1] = (7, "0" * 64)
        self.assertFalse(foundation.is_current())
        connection.rows = []
        self.assertFalse(foundation.is_current())
        self.assertTrue(all(query.startswith("SELECT ") for query in connection.queries))


if __name__ == "__main__":
    unittest.main()
