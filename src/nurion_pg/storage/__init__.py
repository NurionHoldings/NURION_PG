"""Operational persistence boundary."""

from .postgres import OutboxEvent, OutboxRepository, PostgresFoundation

__all__ = ["OutboxEvent", "OutboxRepository", "PostgresFoundation"]
