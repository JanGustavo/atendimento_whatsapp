"""Utilitários compartilhados pelo núcleo da aplicação."""

from datetime import UTC, datetime


def now() -> datetime:
    """Retorna datetime UTC sem timezone (compatível com SQLite DATETIME sem tz)."""
    return datetime.now(UTC).replace(tzinfo=None)
