import httpx

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None  # type: ignore[assignment]

MENU_SELECTORS = {
    "item": ".menu-item, .dish, .product, [class*='menu-item'], [class*='dish']",
    "name": ".name, .title, h3, h4, [class*='name'], [class*='title']",
    "price": ".price, [class*='price'], [class*='cost']",
    "weight": ".weight, .volume, [class*='weight'], [class*='gram']",
    "description": ".description, .desc, [class*='desc']",
}


async def _playwright_fetch(url: str, timeout_ms: int = 60000) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(1000)
        html = await page.content()
        await browser.close()
        return html


async def fetch_html_auto(url: str) -> str:
    """Fetch page HTML; falls back to Playwright when httpx yields <3 dishes."""
    from app.workers.parser import extract_dishes_from_html

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    if len(extract_dishes_from_html(resp.text, MENU_SELECTORS)) < 3:
        return await _playwright_fetch(url)
    return resp.text
