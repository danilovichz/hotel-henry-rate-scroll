"""
Auto EPC login using Playwright.
Handles MFA by waiting for /tmp/mfa_code.txt to be written externally.
"""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv("/Users/rentamac/dani/aios/.env")
import json
import time
from pathlib import Path
from playwright.async_api import async_playwright

SESSION_FILE = Path(__file__).parent / "data" / "epc_session.json"
MFA_SIGNAL = Path("/tmp/waiting_for_mfa.txt")
MFA_CODE_FILE = Path("/tmp/mfa_code.txt")

EPC_LOGIN = "https://www.expediapartnercentral.com/Account/Logon?signedOff=true"
REVPLUS_URL = "https://apps.expediapartnercentral.com/lodging/revplus?htid=9303562"
EMAIL = os.getenv("EPC_EMAIL")
PASSWORD = os.getenv("EPC_PASSWORD")


async def main():
    MFA_SIGNAL.unlink(missing_ok=True)
    MFA_CODE_FILE.unlink(missing_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        context = await browser.new_context()
        page = await context.new_page()

        print("Navigating to EPC login...")
        await page.goto(EPC_LOGIN, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)

        # Accept cookies if banner present
        try:
            await page.click("text=Accept All Cookies", timeout=3000)
            await asyncio.sleep(1)
        except Exception:
            pass

        # Enter email
        print("Entering email...")
        await page.fill('input[type="email"], input[name="email"], input[placeholder="Email"]', EMAIL)
        await page.click('button:has-text("Next"), input[type="submit"]')
        await asyncio.sleep(4)

        # Enter password
        print("Entering password...")
        await page.fill('input[type="password"], input[placeholder="Password"]', PASSWORD)
        try:
            await page.check('input[type="checkbox"]', timeout=2000)  # Keep me signed in
        except Exception:
            pass
        await page.click('button:has-text("Continue"), button:has-text("Sign in"), input[type="submit"]')
        await asyncio.sleep(5)

        # Handle MFA selection screen
        current_url = page.url
        print(f"After password: {current_url}")

        if "mfa" in current_url or "verify" in current_url.lower() or "initiate" in current_url:
            # Click "Continue with Email" if on selection screen
            try:
                await page.click('text=CONTINUE WITH EMAIL', timeout=4000)
                await asyncio.sleep(3)
            except Exception:
                pass

            print("MFA required — writing signal file...")
            MFA_SIGNAL.write_text("waiting")

            # Wait for MFA code file
            print("Waiting for MFA code in /tmp/mfa_code.txt ...")
            for _ in range(120):  # wait up to 2 minutes
                if MFA_CODE_FILE.exists():
                    break
                await asyncio.sleep(1)

            if not MFA_CODE_FILE.exists():
                print("Timed out waiting for MFA code.")
                await browser.close()
                return

            code = MFA_CODE_FILE.read_text().strip()
            print(f"Got MFA code: {code}")

            # Try multiple selectors for the code input
            for selector in [
                'input[placeholder="Enter verification code"]',
                'input[placeholder*="verification"]',
                'input[placeholder*="code"]',
                'input[type="text"]',
            ]:
                try:
                    await page.fill(selector, code, timeout=5000)
                    print(f"Filled code using selector: {selector}")
                    break
                except Exception:
                    continue

            # Click verify
            for selector in ['a:has-text("VERIFY DEVICE")', 'a:has-text("VERIFY")', 'button:has-text("Verify")', '[type="submit"]']:
                try:
                    await page.click(selector, timeout=3000)
                    print(f"Clicked verify using: {selector}")
                    break
                except Exception:
                    continue
            await asyncio.sleep(6)

        # Navigate to RevPlus to get the right session
        print("Navigating to RevPlus...")
        await page.goto(REVPLUS_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        print(f"Final URL: {page.url}")

        # Save session
        cookies = await context.cookies()
        storage = await page.evaluate(
            "() => { try { return JSON.stringify(window.localStorage) } catch(e) { return '{}' } }"
        )
        session_data = {
            "cookies": cookies,
            "local_storage": storage,
            "saved_from_url": page.url,
        }
        SESSION_FILE.parent.mkdir(exist_ok=True)
        SESSION_FILE.write_text(json.dumps(session_data, indent=2))
        print(f"Session saved: {SESSION_FILE}")
        print(f"Cookies saved: {len(cookies)}")

        MFA_SIGNAL.unlink(missing_ok=True)
        MFA_CODE_FILE.unlink(missing_ok=True)
        await asyncio.sleep(3)
        await browser.close()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
