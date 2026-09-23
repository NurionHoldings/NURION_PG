"""Deployment readiness must follow the database, without mutating it."""
import unittest

from fastapi.testclient import TestClient

from nurion_pg.api.app import create_app
from nurion_pg.api.settings import Settings
from nurion_pg.storage.postgres import PostgresFoundation, _checksum


class ReadinessTests(unittest.TestCase):
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
