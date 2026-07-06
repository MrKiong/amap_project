from __future__ import annotations

from pathlib import Path
from typing import Any

from storage.repositories import PreferenceRecord, PreferenceRepository


class FoodMemory:
    def __init__(self, db_path: Path):
        self.repository = PreferenceRepository(db_path)

    def add_preference(self, record: PreferenceRecord) -> int:
        return self.repository.add(record)

    def list_preferences(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.repository.list(limit=limit)

    def preferences_by_category(self, category: str, limit: int = 10) -> list[dict[str, Any]]:
        return self.repository.by_category(category=category, limit=limit)

    def preferences_by_sentiment(self, sentiment: str, limit: int = 10) -> list[dict[str, Any]]:
        return self.repository.by_sentiment(sentiment=sentiment, limit=limit)

    def preference_summary(self) -> str:
        preferences = self.list_preferences(limit=50)
        if not preferences:
            return "暂无明确饮食偏好。"

        parts = []
        grouped: dict[str, list[str]] = {}
        for item in preferences:
            category = str(item.get("category") or "general")
            sentiment = str(item.get("sentiment") or "like")
            preference = str(item.get("preference") or "").strip()
            if not preference:
                continue
            grouped.setdefault(category, []).append(f"{sentiment}: {preference}")

        for category, items in sorted(grouped.items()):
            parts.append(f"{category}: " + "；".join(items[:5]))
        return "\n".join(parts) if parts else "暂无明确饮食偏好。"
