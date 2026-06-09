import re
import csv
import io
import uuid
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


def normalize_price(raw: str) -> float | None:
    if not raw:
        return None
    cleaned = raw.replace("\xa0", " ").replace(" ", "")
    cleaned = re.sub(r"[рублRUBруб\.₽]", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(",", ".").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_dishes_from_html(html: str, selectors: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(selectors.get("item", ".menu-item"))
    results = []
    for item in items:
        name_el = item.select_one(selectors.get("name", ".name"))
        price_el = item.select_one(selectors.get("price", ".price"))
        weight_el = item.select_one(selectors.get("weight", ".weight"))
        desc_el = item.select_one(selectors.get("description", ".description"))

        name = name_el.get_text(strip=True) if name_el else None
        price_raw = price_el.get_text(strip=True) if price_el else None
        price = normalize_price(price_raw) if price_raw else None

        if not name or price is None:
            continue

        results.append({
            "name": name,
            "price": price,
            "weight": weight_el.get_text(strip=True) if weight_el else None,
            "description": desc_el.get_text(strip=True) if desc_el else None,
            "category": None,
        })
    return results


def parse_csv_content(csv_content: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(csv_content))
    results = []
    for row in reader:
        name = row.get("name", "").strip()
        price = normalize_price(row.get("price", ""))
        if not name or price is None:
            continue
        weight = row.get("weight", "").strip() or None
        category = row.get("category", "").strip() or None
        results.append({"name": name, "price": price, "weight": weight, "category": category})
    return results


async def run_parse_job(db: AsyncSession, job_id: uuid.UUID) -> None:
    from app.models.parse_job import ParseJob
    from app.models.venue import Venue
    from app.models.category import Category
    from app.models.dish import Dish

    result = await db.execute(select(ParseJob).where(ParseJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        return

    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    await db.commit()

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http:
            resp = await http.get(job.source_url)
            resp.raise_for_status()

        selectors = {
            "item": ".menu-item, .dish, .product, [class*='menu-item'], [class*='dish']",
            "name": ".name, .title, h3, h4, [class*='name'], [class*='title']",
            "price": ".price, [class*='price'], [class*='cost']",
            "weight": ".weight, .volume, [class*='weight'], [class*='gram']",
            "description": ".description, .desc, [class*='desc']",
        }
        dishes_data = extract_dishes_from_html(resp.text, selectors)

        venue_result = await db.execute(select(Venue).where(Venue.id == job.venue_id))
        venue = venue_result.scalar_one()

        cat_result = await db.execute(
            select(Category).where(Category.venue_id == venue.id, Category.slug == "uncategorized")
        )
        default_cat = cat_result.scalar_one_or_none()
        if not default_cat:
            default_cat = Category(
                id=uuid.uuid4(), venue_id=venue.id, name="Меню", slug="uncategorized", sort_order=0
            )
            db.add(default_cat)
            await db.flush()

        for i, d in enumerate(dishes_data):
            db.add(Dish(
                id=uuid.uuid4(),
                venue_id=venue.id,
                category_id=default_cat.id,
                name=d["name"],
                price=d["price"],
                weight=d.get("weight"),
                description=d.get("description"),
                sort_order=i,
            ))

        job.status = "done"
        job.dishes_found = len(dishes_data)
        job.finished_at = datetime.now(timezone.utc)
        venue.parse_status = "done" if dishes_data else "failed"
        await db.commit()

    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        venue_result = await db.execute(select(Venue).where(Venue.id == job.venue_id))
        venue = venue_result.scalar_one()
        venue.parse_status = "failed"
        await db.commit()
