import asyncio
import os
import smtplib
from playwright.async_api import async_playwright
import httpx

PINBOARDS = [
    "https://also.allthingstalk.com/sp/6644b93d0d5a390001f56634/also:4xbOA7XMcy2XiNN07ujKAMA9XQN4g6clgWhKpVOO",
    # Add more pinboard URLs here
]

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
WAIT_FOR_DATA_TIMEOUT_MS = 30_000  # 30 seconds grace period

async def check_pinboard(page, url: str) -> dict:
    result = {"url": url, "ok": False, "reason": "", "screenshot": None}
    try:
        await page.goto(url, wait_until="networkidle", timeout=60_000)

        # Wait until "Awaiting first data" disappears from ALL widgets
        try:
            await page.wait_for_function(
                "!document.body.innerText.includes('Awaiting first data')",
                timeout=WAIT_FOR_DATA_TIMEOUT_MS
            )
            result["ok"] = True
        except Exception:
            result["reason"] = "One or more widgets still show 'Awaiting first data' after 30s"
            result["screenshot"] = await page.screenshot(full_page=True)

    except Exception as e:
        result["reason"] = f"Page failed to load: {str(e)}"

    return result

async def send_slack_alert(message: str):
    if not SLACK_WEBHOOK_URL:
        print("No SLACK_WEBHOOK_URL set, skipping Slack alert.")
        return
    async with httpx.AsyncClient() as client:
        await client.post(SLACK_WEBHOOK_URL, json={"text": message})

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        failed = []
        for url in PINBOARDS:
            print(f"Checking: {url}")
            result = await check_pinboard(page, url)
            if result["ok"]:
                print(f"  ✅ OK")
            else:
                print(f"  ❌ FAILED: {result['reason']}")
                failed.append(result)

                # Save screenshot locally (also uploaded as GitHub Actions artifact)
                if result["screenshot"]:
                    filename = f"screenshot_{PINBOARDS.index(url)}.png"
                    with open(filename, "wb") as f:
                        f.write(result["screenshot"])

        await browser.close()

        if failed:
            message = "🚨 *ALSO IoT Pinboard Monitor Alert*\n\n"
            for r in failed:
                message += f"• ❌ {r['url']}\n  Reason: {r['reason']}\n\n"
            message += "Screenshots saved as GitHub Actions artifacts."
            await send_slack_alert(message)
            exit(1)  # Non-zero exit marks the GitHub Actions run as failed
        else:
            print("All pinboards OK.")

asyncio.run(main())