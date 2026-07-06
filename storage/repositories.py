from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from storage.db import connect, init_db


@dataclass(frozen=True)
class PreferenceRecord:
    category: str
    preference: str
    sentiment: str = "like"
    weight: int = 1
    source_note: str = ""


class PreferenceRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        init_db(db_path)

    def add(self, record: PreferenceRecord) -> int:
        fields = record.__dataclass_fields__.keys()
        columns = ", ".join(fields)
        placeholders = ", ".join(f":{field}" for field in fields)
        connection = connect(self.db_path)
        try:
            cursor = connection.execute(
                f"INSERT INTO dietary_preferences ({columns}) VALUES ({placeholders})",
                record.__dict__,
            )
            connection.commit()
            return int(cursor.lastrowid)
        finally:
            connection.close()

    def list(self, limit: int = 20) -> list[dict[str, Any]]:
        connection = connect(self.db_path)
        try:
            rows = connection.execute(
                """
                SELECT * FROM dietary_preferences
                ORDER BY weight DESC, updated_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        finally:
            connection.close()
        return [dict(row) for row in rows]

    def by_category(self, category: str, limit: int = 20) -> list[dict[str, Any]]:
        connection = connect(self.db_path)
        try:
            rows = connection.execute(
                """
                SELECT * FROM dietary_preferences
                WHERE category = ?
                ORDER BY weight DESC, updated_at DESC, id DESC
                LIMIT ?
                """,
                (category, limit),
            ).fetchall()
        finally:
            connection.close()
        return [dict(row) for row in rows]

    def by_sentiment(self, sentiment: str, limit: int = 20) -> list[dict[str, Any]]:
        connection = connect(self.db_path)
        try:
            rows = connection.execute(
                """
                SELECT * FROM dietary_preferences
                WHERE sentiment = ?
                ORDER BY weight DESC, updated_at DESC, id DESC
                LIMIT ?
                """,
                (sentiment, limit),
            ).fetchall()
        finally:
            connection.close()
        return [dict(row) for row in rows]
