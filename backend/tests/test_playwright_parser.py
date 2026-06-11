import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_playwright_fetch_returns_page_html():
    """_playwright_fetch returns the page HTML after 3 scrolls."""
    mock_page = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html>menu</html>")
    mock_page.goto = AsyncMock()
    mock_page.evaluate = AsyncMock()
    mock_page.wait_for_timeout = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)
    mock_browser.close = AsyncMock()

    mock_chromium = AsyncMock()
    mock_chromium.launch = AsyncMock(return_value=mock_browser)

    mock_pw_ctx = MagicMock()
    mock_pw_ctx.chromium = mock_chromium
    mock_pw_ctx.__aenter__ = AsyncMock(return_value=mock_pw_ctx)
    mock_pw_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.workers.playwright_parser.async_playwright", return_value=mock_pw_ctx):
        from app.workers.playwright_parser import _playwright_fetch
        result = await _playwright_fetch("http://example.com")

    assert result == "<html>menu</html>"
    mock_page.goto.assert_awaited_once_with(
        "http://example.com", wait_until="networkidle", timeout=60000
    )
    assert mock_page.evaluate.await_count == 3


@pytest.mark.asyncio
async def test_fetch_html_auto_skips_playwright_when_enough_dishes():
    """fetch_html_auto returns httpx HTML directly when ≥3 dishes found."""
    rich_html = """<html><body>
    <div class="menu-item"><span class="name">Борщ</span><span class="price">100</span></div>
    <div class="menu-item"><span class="name">Щи</span><span class="price">90</span></div>
    <div class="menu-item"><span class="name">Котлета</span><span class="price">200</span></div>
    </body></html>"""

    mock_response = MagicMock()
    mock_response.text = rich_html
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.workers.playwright_parser.httpx.AsyncClient", return_value=mock_client), \
         patch("app.workers.playwright_parser._playwright_fetch", new_callable=AsyncMock) as mock_pw:
        import app.workers.playwright_parser as mod
        result = await mod.fetch_html_auto("http://example.com")

    assert result == rich_html
    mock_pw.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_html_auto_uses_playwright_when_sparse():
    """fetch_html_auto calls _playwright_fetch when httpx yields <3 dishes."""
    sparse_html = "<html><body></body></html>"
    playwright_html = "<html><body>full menu content</body></html>"

    mock_response = MagicMock()
    mock_response.text = sparse_html
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.workers.playwright_parser.httpx.AsyncClient", return_value=mock_client), \
         patch("app.workers.playwright_parser._playwright_fetch", new_callable=AsyncMock, return_value=playwright_html) as mock_pw:
        import app.workers.playwright_parser as mod
        result = await mod.fetch_html_auto("http://example.com")

    assert result == playwright_html
    mock_pw.assert_awaited_once_with("http://example.com")
