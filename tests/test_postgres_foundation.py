import unittest
from nurion_pg.storage.postgres import migration_down_sql,migration_up_sql


class PostgresMigrationContractTests(unittest.TestCase):
    def test_migration_contains_versioned_core_and_outbox(self):
        sql=migration_up_sql("nurion_pg_test")
        for table in ("schema_migrations","merchants","principals","api_keys","access_audit","outbox_events"):
            self.assertIn(table,sql)
        self.assertIn("WHERE published_at IS NULL",sql)
        self.assertIn("REFERENCES nurion_pg_test.merchants",sql)

    def test_schema_identifier_is_fail_closed(self):
        for value in ("", "Public", "bad-name", "x; DROP SCHEMA public"):
            with self.assertRaises(ValueError):migration_up_sql(value)

    def test_rollback_orders_foreign_key_dependents_first(self):
        sql=migration_down_sql("nurion_pg_test")
        self.assertLess(sql.index("api_keys"),sql.index("principals"))
        self.assertLess(sql.index("principals"),sql.index("merchants"))


if __name__=="__main__":unittest.main()
