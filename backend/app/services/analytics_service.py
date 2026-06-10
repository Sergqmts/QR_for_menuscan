import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, cast
from sqlalchemy.dialects.postgresql import DATE

from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.dish import Dish
from app.schemas.analytics import AnalyticsOut, AnalyticsSummary, DailyMetric, TopDish


async def get_analytics(
    db: AsyncSession,
    venue_id: uuid.UUID,
    from_date: datetime,
    to_date: datetime,
) -> AnalyticsOut:
    base_filter = [
        Order.venue_id == venue_id,
        Order.created_at >= from_date,
        Order.created_at < to_date,
        Order.status != "cancelled",
    ]

    summary_stmt = select(
        func.count(Order.id).label("orders"),
        func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
        func.coalesce(func.avg(Order.total_amount), 0).label("avg_check"),
    ).where(*base_filter)

    daily_stmt = (
        select(
            cast(Order.created_at, DATE).label("date"),
            func.sum(Order.total_amount).label("revenue"),
            func.count(Order.id).label("orders"),
        )
        .where(*base_filter)
        .group_by(cast(Order.created_at, DATE))
        .order_by(cast(Order.created_at, DATE))
    )

    top_stmt = (
        select(
            Dish.name,
            func.count(OrderItem.id).label("count"),
            func.sum(OrderItem.unit_price * OrderItem.quantity).label("revenue"),
        )
        .join(Dish, Dish.id == OrderItem.dish_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(*base_filter)
        .group_by(Dish.id, Dish.name)
        .order_by(func.count(OrderItem.id).desc())
        .limit(10)
    )

    summary_result = await db.execute(summary_stmt)
    daily_result = await db.execute(daily_stmt)
    top_result = await db.execute(top_stmt)

    summary_row = summary_result.one()
    top_rows = top_result.all()

    return AnalyticsOut(
        summary=AnalyticsSummary(
            orders=summary_row.orders,
            revenue=Decimal(str(summary_row.revenue)),
            avg_check=Decimal(str(summary_row.avg_check)),
            top_dish=top_rows[0].name if top_rows else None,
        ),
        daily=[
            DailyMetric(
                date=row.date,
                revenue=Decimal(str(row.revenue)),
                orders=row.orders,
            )
            for row in daily_result.all()
        ],
        top_dishes=[
            TopDish(
                name=row.name,
                count=row.count,
                revenue=Decimal(str(row.revenue)),
            )
            for row in top_rows
        ],
    )
