import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://happylilac.net/jhs-math.html")
        links = await page.locator("a").all()
        for link in links:
            text = await link.inner_text()
            href = await link.get_attribute("href")
            if href and "jhs-math" in href:
                print(f"{text.strip()[:20]} => {href}")
        await browser.close()
asyncio.run(main())
