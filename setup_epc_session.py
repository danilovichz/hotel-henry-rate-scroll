#!/usr/bin/env python3
"""
EPC Session Setup — One-time manual login for Expedia Partner Central.

Opens your real Chrome browser. Log in manually (including MFA).
The script watches the URL — once it detects you're on the EPC dashboard,
it saves the session automatically. You don't need to press anything.

Usage:
  python3 setup_epc_session.py
"""

import json
import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

SESSION_FILE = Path(__file__).parent / "data" / "epc_session.json"
EPC_URL = "https://apps.expediapartnercentral.com/"

# URLs that mean we're successfully logged in
SUCCESS_URL_FRAGMENTS = [
    "apps.expediapartnercentral.com",
]

# URLs that mean we're still on login/MFA
LOGIN_URL_FRAGMENTS = [
    "logon",
    "login",
    "accounts.expediagroup.com",
    "mfa",
    "password",
]


async def main():
    print("=" * 60)
    print("EPC SESSION SETUP")
    print("=" * 60)
    print()
    print("Your Chrome browser will open.")
    print("Log in to Expedia Partner Central (including MFA code).")
    print()
    print("Once you reach the EPC dashboard, the session saves")
    print("automatically — you don't need to press anything here.")
    print()
    print("Waiting for Chrome to open...")
    print()

    async with async_playwright() as p:
        # Try system Chrome first, fall back to Playwright's Chromium
        try:
            browser = await p.chromium.launch(
                channel="chrome",
                headless=False,
                slow_mo=50,
                args=["--start-maximized"],
            )
            print("Using your installed Chrome.")
        except Exception:
            print("System Chrome not found — using Playwright Chromium.")
            browser = await p.chromium.launch(
                headless=False,
                slow_mo=50,
                args=["--start-maximized"],
            )

        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        await page.goto(EPC_URL)
        print("Browser opened. Log in now (including MFA)...")
        print()

        # Poll until we detect the user is on the dashboard
        check_interval = 2  # seconds
        max_wait = 300  # 5 minutes
        elapsed = 0

        while elapsed < max_wait:
            await asyncio.sleep(check_interval)
            elapsed += check_interval

            try:
                current_url = page.url
            except Exception:
                print("Browser was closed. Exiting.")
                sys.exit(1)

            is_login = any(frag in current_url.lower() for frag in LOGIN_URL_FRAGMENTS)
            is_dashboard = (
                any(frag in current_url for frag in SUCCESS_URL_FRAGMENTS)
                and not is_login
            )

            if elapsed % 10 == 0:
                print(f"  Still waiting... current URL: {current_url[:80]}")

            if is_dashboard:
                print()
                print(f"Logged in! URL: {current_url}")
                print("Saving session...")
                await asyncio.sleep(2)  # Let page fully settle

                cookies = await context.cookies()
                storage = await page.evaluate(
                    "() => { try { return JSON.stringify(window.localStorage) } catch(e) { return '{}' } }"
                )

                session_data = {
                    "cookies": cookies,
                    "local_storage": storage,
                    "saved_from_url": current_url,
                }

                SESSION_FILE.parent.mkdir(exist_ok=True)
                SESSION_FILE.write_text(json.dumps(session_data, indent=2))

                print(f"Session saved: {SESSION_FILE}")
                print(f"Cookies saved: {len(cookies)}")
                print()
                print("Done. Close the browser window — setup is complete.")
                print("Run: python3 collect_epc_rates.py --debug")
                await asyncio.sleep(5)
                await browser.close()
                return

        print("Timed out after 5 minutes. Please try again.")
        await browser.close()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
