import re
import csv
import io
import uuid
from datetime import datetime, timezone

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

    # Strategy 1: standard CSS selectors (generic menu markup)
    results = _extract_by_css(soup, selectors)
    if results:
        return results

    # Strategy 2: data-prod-* attributes (iiko WebMenu, secret-kitchen style)
    results = _extract_by_data_prod(soup)
    if results:
        return results

    # Strategy 3: JSON-LD structured data (schema.org/MenuItem)
    results = _extract_by_jsonld(soup)
    if results:
        return results

    # Strategy 4: heuristic — elements whose text matches price pattern
    results = _extract_by_price_heuristic(soup)
    return results


def _extract_by_css(soup: BeautifulSoup, selectors: dict) -> list[dict]:
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


def _extract_by_data_prod(soup: BeautifulSoup) -> list[dict]:
    """Handle sites that store dish data in data-prod-* attributes (iiko WebMenu, etc.)."""
    items = soup.select("[data-prod-name][data-prod-price]")
    results = []
    seen = set()
    for item in items:
        name = item.get("data-prod-name", "").strip()
        price = normalize_price(item.get("data-prod-price", ""))
        if not name or price is None:
            continue
        key = (name.lower(), price)
        if key in seen:
            continue
        seen.add(key)
        category = item.get("data-prod-category") or item.get("data-category") or None
        weight = item.get("data-prod-weight") or item.get("data-weight") or None
        results.append({"name": name, "price": price, "weight": weight, "description": None, "category": category})
    return results


def _extract_by_jsonld(soup: BeautifulSoup) -> list[dict]:
    """Extract schema.org/MenuItem from JSON-LD script tags."""
    import json
    results = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for obj in items:
            if not isinstance(obj, dict):
                continue
            # unwrap @graph
            if obj.get("@type") == "Restaurant" and "hasMenu" in obj:
                has_menu = obj["hasMenu"]
                # hasMenu can be a single dict or a list of menu objects
                candidates = has_menu if isinstance(has_menu, list) else [has_menu]
            else:
                candidates = [obj]
            for menu_obj in candidates:
                if not isinstance(menu_obj, dict):
                    continue
                if menu_obj.get("@type") not in ("Menu", "MenuSection"):
                    continue
                for section in menu_obj.get("hasMenuSection", [menu_obj]):
                    if not isinstance(section, dict):
                        continue
                    for entry in section.get("hasMenuItem", []):
                        if not isinstance(entry, dict):
                            continue
                        name = entry.get("name", "").strip()
                        offer = entry.get("offers", {})
                        if isinstance(offer, list):
                            offer = offer[0] if offer else {}
                        price = normalize_price(str(offer.get("price", "")))
                        if not name or price is None:
                            continue
                        results.append({
                            "name": name,
                            "price": price,
                            "weight": None,
                            "description": entry.get("description"),
                            "category": section.get("name"),
                        })
    return results


def _extract_by_price_heuristic(soup: BeautifulSoup) -> list[dict]:
    """Last resort: find any element containing a price next to a name-like sibling."""
    _PRICE_RE = re.compile(r"^\s*(\d[\d\s]*)\s*(?:руб|₽|р\.?)\s*$", re.IGNORECASE)
    results = []
    seen = set()
    for el in soup.find_all(True):
        text = el.get_text(strip=True)
        m = _PRICE_RE.match(text)
        if not m:
            continue
        price = normalize_price(m.group(1))
        if price is None or price < 10 or price > 100_000:
            continue
        # look for a name sibling or parent heading
        parent = el.parent
        if parent is None:
            continue
        siblings = [s for s in parent.children if hasattr(s, "get_text") and s is not el]
        name = next((s.get_text(strip=True) for s in siblings if 3 < len(s.get_text(strip=True)) < 120), None)
        if not name:
            continue
        key = (name.lower(), price)
        if key in seen:
            continue
        seen.add(key)
        results.append({"name": name, "price": price, "weight": None, "description": None, "category": None})
        if len(results) >= 300:
            break
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


def _compute_diff(existing_dishes: list, parsed_dishes: list) -> list[dict]:
    existing_by_name = {d.name.lower(): d for d in existing_dishes}
    parsed_names = {d["name"].lower() for d in parsed_dishes}
    diff = []

    for parsed in parsed_dishes:
        name_key = parsed["name"].lower()
        if name_key in existing_by_name:
            existing = existing_by_name[name_key]
            changes = {}
            if parsed.get("price") is not None and abs(float(existing.price) - float(parsed["price"])) > 0.01:
                changes["old_price"] = float(existing.price)
                changes["new_price"] = float(parsed["price"])
            if parsed.get("weight") and parsed["weight"] != existing.weight:
                changes["old_weight"] = existing.weight
                changes["new_weight"] = parsed["weight"]
            if changes:
                diff.append({
                    "dish_id": str(existing.id),
                    "action": "update",
                    "name": existing.name,
                    **changes,
                })
        else:
            diff.append({
                "dish_id": None,
                "action": "add",
                "name": parsed["name"],
                "new_price": float(parsed["price"]),
                "new_weight": parsed.get("weight"),
                "description": parsed.get("description"),
            })

    for name_key, existing in existing_by_name.items():
        if name_key not in parsed_names:
            diff.append({
                "dish_id": str(existing.id),
                "action": "remove",
                "name": existing.name,
                "old_price": float(existing.price),
            })

    return diff


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
        from app.workers.playwright_parser import fetch_html_auto, MENU_SELECTORS
        html = await fetch_html_auto(job.source_url)
        dishes_data = extract_dishes_from_html(html, MENU_SELECTORS)

        venue_result = await db.execute(select(Venue).where(Venue.id == job.venue_id))
        venue = venue_result.scalar_one()

        if job.diff_mode:
            existing_result = await db.execute(select(Dish).where(Dish.venue_id == venue.id))
            existing_dishes = existing_result.scalars().all()
            diff = _compute_diff(existing_dishes, dishes_data)
            job.diff_data = diff
            job.status = "done"
            job.dishes_found = len(dishes_data)
            job.finished_at = datetime.now(timezone.utc)
            venue.parse_status = "done"
            await db.commit()
            return

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
        # Roll back any partial transaction before writing failure state.
        await db.rollback()
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        venue_result = await db.execute(select(Venue).where(Venue.id == job.venue_id))
        venue = venue_result.scalar_one_or_none()
        if venue:
            venue.parse_status = "failed"
        await db.commit()
