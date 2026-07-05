from __future__ import annotations

from pathlib import Path
from typing import Any

from storage.repositories import MealRecord, MealRepository


class FoodMemory:
    def __init__(self, db_path: Path):
        self.repository = MealRepository(db_path)

    def add_meal(self, record: MealRecord) -> int:
        return self.repository.add(record)

    def recent_meals(self, limit: int = 10) -> list[dict[str, Any]]:
        return self.repository.list(limit=limit)

    def search_by_cuisine(self, cuisine: str, limit: int = 10) -> list[dict[str, Any]]:
        return self.repository.by_cuisine(cuisine=cuisine, limit=limit)

    def high_rated(self, min_rating: float = 4.0, limit: int = 10) -> list[dict[str, Any]]:
        return self.repository.by_min_rating(rating=min_rating, limit=limit)

    def pitfalls(self, limit: int = 10) -> list[dict[str, Any]]:
        return self.repository.pitfalls(limit=limit)

    def preference_summary(self) -> str:
        meals = self.recent_meals(limit=50)
        if not meals:
            return "暂无历史用餐记录。"

        cuisine_scores: dict[str, list[float]] = {}
        positives: list[str] = []
        negatives: list[str] = []
        for meal in meals:
            cuisine = meal.get("cuisine") or "未标注菜系"
            rating = meal.get("rating")
            if rating is not None:
                cuisine_scores.setdefault(cuisine, []).append(float(rating))
            if meal.get("pros"):
                positives.append(str(meal["pros"]))
            if meal.get("cons"):
                negatives.append(str(meal["cons"]))

        cuisine_bits = []
        for cuisine, scores in sorted(
            cuisine_scores.items(),
            key=lambda item: sum(item[1]) / len(item[1]),
            reverse=True,
        )[:5]:
            avg = sum(scores) / len(scores)
            cuisine_bits.append(f"{cuisine}平均评分{avg:.1f}")

        parts = []
        if cuisine_bits:
            parts.append("偏好菜系：" + "；".join(cuisine_bits))
        if positives:
            parts.append("喜欢的体验：" + "；".join(positives[:5]))
        if negatives:
            parts.append("踩雷点：" + "；".join(negatives[:5]))
        return "\n".join(parts) if parts else "已有历史记录，但偏好信号还不明显。"
