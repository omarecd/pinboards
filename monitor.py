import asyncio
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from playwright.async_api import async_playwright

PINBOARDS = [
    "https://also.allthingstalk.com/sp/6644b93d0d5a390001f56634/also:4xbOA7XMcy2XiNN07ujKAMA9XQN4g6clgWhKpVOO",
    # Add more pinboard URLs here
]

SMTP_HOST     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER     = os.environ.get("SMTP_USER")       # your sending email address
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")   # your email password or app password
ALERT_TO      = os.environ.get("ALERT_TO")        # recipient email address

WAIT_FOR_DATA_TIMEOUT_MS = 30_000  # 30 seconds grace period

async def check_pinboard(page, url: str) -> dict:
    result = {"url": url, "ok": False, "reason": "", "screenshot": None}
    try:
        await page.goto(url, wait_until="networkidle", timeout=60_000)

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

def send_email_alert(failed: list):
    msg = MIMEMultipart("mixed")
    msg["Subject"] = "🚨 ALSO IoT Pinboard Monitor Alert"
    msg["From"]    = SMTP_USER
    msg["To"]      = ALERT_TO

    # Build HTML body
    body = "<h2>🚨 ALSO IoT Pinboard Monitor Alert</h2>"
    body += "<p>The following pinboards failed to load data:</p><ul>"
    for i, r in enumerate(failed):
        body += f"<li><b>{r['url']}</b><br/>Reason: {r['reason']}</li>"
        if r["screenshot"]:
            body += f"<br/><img src='cid:screenshot_{i}'/>"
    body += "</ul>"
    body += "<p>Please investigate as soon as possible.</p>"

    msg.attach(MIMEText(body, "html"))

    # Attach screenshots inline
    for i, r in enumerate(failed):
        if r["screenshot"]:
            img = MIMEImage(r["screenshot"])
            img.add_header("Content-ID", f"<screenshot_{i}>")
            img.add_header("Content-Disposition", "inline", filename=f"screenshot_{i}.png")
            msg.attach(img)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, ALERT_TO, msg.as_string())

    print(f"Alert email sent to {ALERT_TO}")

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

                if result["screenshot"]:
                    filename = f"screenshot_{PINBOARDS.index(url)}.png"
                    with open(filename, "wb") as f:
                        f.write(result["screenshot"])

        await browser.close()

        if failed:
            send_email_alert(failed)
            exit(1)
        else:
            print("All pinboards OK.")

asyncio.run(main())
