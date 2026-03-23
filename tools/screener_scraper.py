import asyncio
from playwright.async_api import async_playwright
from typing import List, Dict
import os

SCREENER_EMAIL = os.getenv("SCREENER_EMAIL")
SCREENER_PASSWORD = os.getenv("SCREENER_PASSWORD")

async def scrape_screener(query: str) -> List[Dict]:
    """
    Logs into Screener.in, runs a query, returns list of stock dicts.
    Works by automating the browser — no API needed.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"
        )
        page = await context.new_page()

        # Step A: Login
        await page.goto("https://www.screener.in/login/")
        
        # If the environment variables are not set, return empty results early
        if not SCREENER_EMAIL or not SCREENER_PASSWORD:
            print("Warning: Screener.in credentials not set in .env")
            await browser.close()
            return []
            
        await page.fill('input[name="username"]', SCREENER_EMAIL)
        await page.fill('input[name="password"]', SCREENER_PASSWORD)
        await page.click('button[type="submit"]')
        await page.wait_for_url("**/dash/**", timeout=10000)

        # Step B: Navigate to screen page
        await page.goto("https://www.screener.in/screen/raw/")
        await page.wait_for_selector('textarea#id_query', timeout=8000)

        # Step C: Clear existing query and type new one
        await page.fill('textarea#id_query', query)
        await page.click('button[type="submit"]')

        # Step D: Wait for results table
        await page.wait_for_selector('table.data-table', timeout=15000)

        # Step E: Parse results table
        stocks = await page.evaluate("""
            () => {
                const rows = [];
                const headers = [...document.querySelectorAll('table.data-table thead th')]
                    .map(h => h.innerText.trim());
                document.querySelectorAll('table.data-table tbody tr').forEach(row => {
                    const cells = [...row.querySelectorAll('td')].map(c => c.innerText.trim());
                    if (cells.length > 0) {
                        const obj = {};
                        headers.forEach((h, i) => obj[h] = cells[i] || '');
                        // grab the NSE ticker from the link
                        const link = row.querySelector('a');
                        if (link) obj['url'] = link.href;
                        rows.push(obj);
                    }
                });
                return rows;
            }
        """)

        await browser.close()
        return stocks


def run_screener_query(query: str) -> List[Dict]:
    """Sync wrapper for ADK tool use"""
    return asyncio.run(scrape_screener(query))
