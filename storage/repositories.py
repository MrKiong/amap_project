from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from storage.db import connect, init_db


@dataclass(frozen=True)
class MealRecord:
    restaurant_name: str
    location: str = ""
    cuisine: str = ""
    avg_price: float | None = None
    rating: float | None = None
    dishes: str = ""
    scenario: str = ""
    companions: str = ""
    comment: str = ""
    pros: str = ""
    cons: str = ""
    revisit_willingness: str = ""


class MealRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        init_db(db_path)

    def add(self, record: MealRecord) -> int:
        fields = record.__dataclass_fields__.keys()
        columns = ", ".join(fields)
        placeholders = ", ".join(f":{field}" for field in fields)
        connection = connect(self.db_path)
        try:
            cursor = connection.execute(
                f"INSERT INTO meals ({columns}) VALUES ({placeholders})",
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
                "SELECT * FROM meals ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        finally:
            connection.close()
        return [dict(row) for row in rows]

    def by_cuisine(self, cuisine: str, limit: int = 20) -> list[dict[str, Any]]:
        connection = connect(self.db_path)
        try:
            rows = connection.execute(
                """
                SELECT * FROM meals
                WHERE cuisine LIKE ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (f"%{cuisine}%", limit),
            ).fetchall()
        finally:
            connection.close()
        return [dict(row) for row in rows]

    def by_min_rating(self, rating: float, limit: int = 20) -> list[dict[str, Any]]:
        connection = connect(self.db_path)
        try:
            rows = connection.execute(
                """
                SELECT * FROM meals
                WHERE rating >= ?
                ORDER BY rating DESC, created_at DESC, id DESC
                LIMIT ?
                """,
                (rating, limit),
            ).fetchall()
        finally:
            connection.close()
        return [dict(row) for row in rows]

    def pitfalls(self, limit: int = 20) -> list[dict[str, Any]]:
        connection = connect(self.db_path)
        try:
            rows = connection.execute(
                """
                SELECT * FROM meals
                WHERE (rating IS NOT NULL AND rating <= 2.5)
                   OR revisit_willingness IN ('no', 'false', '不愿意', '否')
                   OR cons != ''
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        finally:
            connection.close()
        return [dict(row) for row in rows]
