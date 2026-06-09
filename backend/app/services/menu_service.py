from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.models.venue import Venue
from app.models.category import Category
from app.models.dish import Dish
from app.schemas.menu import PublicMenuOut, PublicVenueOut, PublicCategoryOut, PublicDishOut


async def get_public_menu(db: AsyncSession, venue_slug: str) -> PublicMenuOut:
    result = await db.execute(select(Venue).where(Venue.slug == venue_slug, Venue.is_active == True))
    venue = result.scalar_one_or_none()
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")

    cats_result = await db.execute(
        select(Category).where(Category.venue_id == venue.id, Category.is_visible == True)
        .order_by(Category.sort_order)
    )
    categories = cats_result.scalars().all()

    dishes_result = await db.execute(
        select(Dish).where(Dish.venue_id == venue.id, Dish.is_available == True).order_by(Dish.sort_order)
    )
    dishes_by_cat: dict = {}
    for dish in dishes_result.scalars().all():
        dishes_by_cat.setdefault(str(dish.category_id), []).append(dish)

    return PublicMenuOut(
        venue=PublicVenueOut(id=venue.id, name=venue.name, logo_url=venue.logo_url, settings=venue.settings),
        categories=[
            PublicCategoryOut(
                id=cat.id, name=cat.name, slug=cat.slug, sort_order=cat.sort_order,
                dishes=[PublicDishOut.model_validate(d) for d in dishes_by_cat.get(str(cat.id), [])]
            )
            for cat in categories
        ],
    )
