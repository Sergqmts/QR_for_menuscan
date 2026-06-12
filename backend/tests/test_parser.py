import pytest
from app.workers.parser import normalize_price, extract_dishes_from_html, parse_csv_content


def test_normalize_price_integer():
    assert normalize_price("350") == 350.0


def test_normalize_price_with_rub():
    assert normalize_price("350 руб") == 350.0


def test_normalize_price_with_spaces():
    assert normalize_price("1 200 руб.") == 1200.0


def test_normalize_price_decimal():
    assert normalize_price("299,90") == 299.9


def test_normalize_price_invalid():
    assert normalize_price("бесплатно") is None


def test_extract_dishes_from_html_basic():
    html = """
    <html><body>
    <div class="menu-item">
        <span class="name">Борщ</span>
        <span class="price">350 руб</span>
        <span class="weight">300мл</span>
    </div>
    <div class="menu-item">
        <span class="name">Котлета</span>
        <span class="price">420 руб</span>
    </div>
    </body></html>
    """
    dishes = extract_dishes_from_html(html, selectors={
        "item": ".menu-item",
        "name": ".name",
        "price": ".price",
        "weight": ".weight",
    })
    assert len(dishes) == 2
    assert dishes[0]["name"] == "Борщ"
    assert dishes[0]["price"] == 350.0
    assert dishes[0]["weight"] == "300мл"
    assert dishes[1]["name"] == "Котлета"
    assert dishes[1]["price"] == 420.0


def test_extract_dishes_empty_html():
    dishes = extract_dishes_from_html("<html></html>", selectors={
        "item": ".menu-item", "name": ".name", "price": ".price"
    })
    assert dishes == []


def test_parse_csv():
    csv_content = "name,price,weight,category\nБорщ,350,300мл,Супы\nКотлета,420,,Горячее"
    dishes = parse_csv_content(csv_content)
    assert len(dishes) == 2
    assert dishes[0] == {"name": "Борщ", "price": 350.0, "weight": "300мл", "category": "Супы"}
    assert dishes[1] == {"name": "Котлета", "price": 420.0, "weight": None, "category": "Горячее"}


def test_extract_by_jsonld_flat_menu():
    """schema.org/Menu with hasMenuSection."""
    import json
    payload = {
        "@type": "Menu",
        "hasMenuSection": [
            {
                "name": "Супы",
                "hasMenuItem": [
                    {"name": "Борщ", "offers": {"price": "350"}},
                    {"name": "Щи", "offers": {"price": "300"}},
                ],
            }
        ],
    }
    html = f'<html><head><script type="application/ld+json">{json.dumps(payload)}</script></head></html>'
    dishes = extract_dishes_from_html(html, selectors={})
    assert len(dishes) == 2
    assert dishes[0]["name"] == "Борщ"
    assert dishes[0]["price"] == 350.0
    assert dishes[0]["category"] == "Супы"


def test_extract_by_jsonld_restaurant_with_menu_list():
    """Restaurant.hasMenu is a LIST — previously crashed with AttributeError."""
    import json
    payload = {
        "@type": "Restaurant",
        "hasMenu": [
            {
                "@type": "Menu",
                "hasMenuSection": [
                    {
                        "name": "Горячее",
                        "hasMenuItem": [
                            {"name": "Котлета", "offers": {"price": "420"}},
                        ],
                    }
                ],
            }
        ],
    }
    html = f'<html><head><script type="application/ld+json">{json.dumps(payload)}</script></head></html>'
    dishes = extract_dishes_from_html(html, selectors={})
    assert len(dishes) == 1
    assert dishes[0]["name"] == "Котлета"
    assert dishes[0]["price"] == 420.0


def test_extract_by_jsonld_offers_as_list():
    """offers can be a list instead of a dict."""
    import json
    payload = {
        "@type": "Menu",
        "hasMenuSection": [
            {
                "name": "Напитки",
                "hasMenuItem": [
                    {"name": "Чай", "offers": [{"price": "150"}]},
                ],
            }
        ],
    }
    html = f'<html><head><script type="application/ld+json">{json.dumps(payload)}</script></head></html>'
    dishes = extract_dishes_from_html(html, selectors={})
    assert len(dishes) == 1
    assert dishes[0]["name"] == "Чай"
    assert dishes[0]["price"] == 150.0


def test_extract_by_data_prod():
    """Dishes via data-prod-* attributes (iiko WebMenu style)."""
    html = """
    <html><body>
    <div data-prod-name="Пицца Маргарита" data-prod-price="590" data-prod-category="Пицца"></div>
    <div data-prod-name="Пицца Пепперони" data-prod-price="650" data-prod-category="Пицца"></div>
    </body></html>
    """
    dishes = extract_dishes_from_html(html, selectors={})
    assert len(dishes) == 2
    assert dishes[0]["name"] == "Пицца Маргарита"
    assert dishes[0]["price"] == 590.0
    assert dishes[0]["category"] == "Пицца"
