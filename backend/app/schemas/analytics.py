from datetime import date as DateType
from pydantic import BaseModel
from decimal import Decimal


class DailyMetric(BaseModel):
    date: DateType
    revenue: Decimal
    orders: int


class TopDish(BaseModel):
    name: str
    count: int
    revenue: Decimal


class AnalyticsSummary(BaseModel):
    orders: int
    revenue: Decimal
    avg_check: Decimal
    top_dish: str | None


class AnalyticsOut(BaseModel):
    summary: AnalyticsSummary
    daily: list[DailyMetric]
    top_dishes: list[TopDish]
