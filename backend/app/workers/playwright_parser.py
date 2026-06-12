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


async def _playwright_fetch(url: str, timeout_ms: int = 90000) -> str:
    if async_playwright is None:
        raise RuntimeError("playwright is not installed; install backend[worker]")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page(
                extra_http_headers={
                    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                }
            )
            # Use domcontentloaded — networkidle never triggers on SPAs with polling
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            # Give JS time to render initial content, then scroll to trigger lazy loads
            await page.wait_for_timeout(3000)
            for _ in range(4):
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await page.wait_for_timeout(1500)
            # Wait for any price-like element to appear (up to 10 more seconds)
            try:
                await page.wait_for_selector(
                    "[class*='price'],[class*='cost'],[data-prod-price]",
                    timeout=10000,
                )
            except Exception:
                pass  # proceed even if no price selector found
            return await page.content()
        finally:
            await browser.close()


_JS_FRAMEWORK_SIGNS = (
    # Vue / Angular / React template / SPA indicators in raw HTML
    "{{", "ng-app", "ng-controller", "v-for", "x-data",
    "__NEXT_DATA__", "__nuxt", "window.__",
    # Bitrix CMS JS-rendered catalog
    "BX.ready", "BXMainpageSlider",
)

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


def _looks_like_spa(html: str) -> bool:
    """Return True if the HTML looks like a JS-rendered SPA that needs Playwright."""
    head = html[:8000]
    return any(sign in head for sign in _JS_FRAMEWORK_SIGNS)


async def fetch_html_auto(url: str) -> str:
    """Fetch page HTML; uses Playwright for JS-rendered SPAs, httpx for static pages."""
    from app.workers.parser import extract_dishes_from_html

    try:
        async with httpx.AsyncClient(
            timeout=30.0, follow_redirects=True, headers=_BROWSER_HEADERS
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        # Skip Playwright if the page is clearly a static menu with enough dishes
        if not _looks_like_spa(resp.text):
            dishes = extract_dishes_from_html(resp.text, MENU_SELECTORS)
            if len(dishes) >= 3:
                return resp.text

    except httpx.HTTPError:
        pass

    return await _playwright_fetch(url)
