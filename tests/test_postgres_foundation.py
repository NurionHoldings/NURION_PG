import unittest
from nurion_pg.storage.postgres import MIGRATION_VERSION,OutboxRepository,PostgresFoundation,migration_down_sql,migration_up_sql


class PostgresMigrationContractTests(unittest.TestCase):
    def test_migration_contains_versioned_core_and_outbox(self):
        sql=migration_up_sql("nurion_pg_test")
        for table in ("schema_migrations","merchants","principals","api_keys","access_audit","outbox_events"):
            self.assertIn(table,sql)
        self.assertIn("WHERE published_at IS NULL",sql)
        self.assertIn("REFERENCES nurion_pg_test.merchants",sql)
        self.assertIn("available_at",sql)
        self.assertIn("lease_owner",sql)
        for table in ("payment_intents","payment_operations","payment_command_receipts"):
            self.assertIn(table,sql)
        self.assertEqual(MIGRATION_VERSION,5)
        self.assertIn("provider_webhook_inbox",sql)

    def test_schema_identifier_is_fail_closed(self):
        for value in ("", "Public", "bad-name", "x; DROP SCHEMA public"):
            with self.assertRaises(ValueError):migration_up_sql(value)

    def test_rollback_orders_foreign_key_dependents_first(self):
        sql=migration_down_sql("nurion_pg_test")
        self.assertLess(sql.index("api_keys"),sql.index("principals"))
        self.assertLess(sql.index("principals"),sql.index("merchants"))

    def test_foundation_rejects_implicit_transaction_connections(self):
        connection=type("Connection",(),{"autocommit":False})()
        with self.assertRaises(ValueError):PostgresFoundation(connection)

    def test_outbox_rejects_unsafe_parameters(self):
        repository=OutboxRepository(type("Connection",(),{"autocommit":True})())
        for args in (("",1,60),("worker",0,60),("worker",1001,60),("worker",1,0)):
            with self.assertRaises(ValueError):repository.claim(*args)
        with self.assertRaises(ValueError):repository.mark_failed("event","worker","",30)


if __name__=="__main__":unittest.main()
