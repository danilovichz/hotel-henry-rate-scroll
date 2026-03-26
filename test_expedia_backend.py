"""
Test Firecrawl's ability to scrape Expedia Partner Central backend.

Steps:
1. Screenshot the login page to see what we're working with
2. Attempt login with credentials
3. Navigate to Revenue Management rate shop
4. Extract competitor rate data
"""

import os
import sys
import json
import base64
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load API key from AIOS .env
load_dotenv("/Users/rentamac/dani/aios/.env")
API_KEY = os.getenv("FIRECRAWL_API_KEY")
ENDPOINT = "https://api.firecrawl.dev/v1/scrape"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

USERNAME = "hotelhenryhig@gmail.com"
PASSWORD = "HenryClaw92108!"

SCREENSHOTS_DIR = Path(__file__).parent / "data" / "firecrawl_screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def save_screenshot(response_data, filename):
    """Save base64 screenshot from Firecrawl response if present."""
    # Firecrawl returns screenshot in actions_result or as screenshot field
    screenshot = None
    if isinstance(response_data, dict):
        # Check common locations for screenshot data
        for key_path in [
            lambda d: d.get("data", {}).get("screenshot"),
            lambda d: d.get("data", {}).get("actions", {}).get("screenshots", [None])[0],
            lambda d: d.get("screenshot"),
        ]:
            try:
                val = key_path(response_data)
                if val:
                    screenshot = val
                    break
            except (IndexError, TypeError, AttributeError):
                continue

    if screenshot:
        # Strip data URI prefix if present
        if screenshot.startswith("data:"):
            screenshot = screenshot.split(",", 1)[1]
        filepath = SCREENSHOTS_DIR / filename
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(screenshot))
        print(f"  -> Screenshot saved: {filepath}")
        return True
    else:
        print("  -> No screenshot found in response")
        return False


def firecrawl_request(payload, label="request"):
    """Send a request to Firecrawl and return the response."""
    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"{'='*60}")
    print(f"URL: {payload.get('url')}")
    print(f"Actions: {len(payload.get('actions', []))} steps")

    try:
        resp = requests.post(ENDPOINT, headers=HEADERS, json=payload, timeout=120)
        print(f"HTTP Status: {resp.status_code}")

        try:
            data = resp.json()
        except Exception:
            print(f"Raw response: {resp.text[:2000]}")
            return None

        # Print response (truncate large fields for readability)
        display = json.loads(json.dumps(data))
        # Truncate screenshot/base64 fields for display
        def truncate_b64(obj):
            if isinstance(obj, dict):
                return {k: ("...[base64 truncated]..." if isinstance(v, str) and len(v) > 500 and ("base64" in k.lower() or "screenshot" in k.lower() or v.startswith("data:")) else truncate_b64(v)) for k, v in obj.items()}
            if isinstance(obj, list):
                return [truncate_b64(i) for i in obj]
            if isinstance(obj, str) and len(obj) > 2000:
                return obj[:500] + f"... [{len(obj)} chars total]"
            return obj

        print(f"\nResponse JSON:")
        print(json.dumps(truncate_b64(display), indent=2))

        return data

    except requests.exceptions.Timeout:
        print("ERROR: Request timed out (120s)")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def test_1_screenshot_login_page():
    """Just load the login page and screenshot it to see what's there."""
    payload = {
        "url": "https://apps.expediapartnercentral.com/",
        "formats": ["screenshot", "html"],
        "actions": [
            {"type": "wait", "milliseconds": 3000},
            {"type": "screenshot"},
        ],
    }
    data = firecrawl_request(payload, "1 — Screenshot login page")
    if data:
        save_screenshot(data, "01_login_page.png")
    return data


def test_2_try_login_generic_selectors():
    """Attempt login using common/generic selectors."""
    payload = {
        "url": "https://apps.expediapartnercentral.com/",
        "formats": ["screenshot", "html"],
        "actions": [
            {"type": "wait", "milliseconds": 3000},
            {"type": "screenshot"},
            # Try generic input selectors — email first
            {"type": "click", "selector": "input[type='email'], input[name='email'], input[id*='email'], input[id*='user'], input[name*='user'], input[type='text']"},
            {"type": "write", "text": USERNAME},
            {"type": "wait", "milliseconds": 500},
            # Try password field
            {"type": "click", "selector": "input[type='password'], input[name='password'], input[id*='password']"},
            {"type": "write", "text": PASSWORD},
            {"type": "wait", "milliseconds": 500},
            {"type": "screenshot"},
            # Try submit
            {"type": "click", "selector": "button[type='submit'], input[type='submit'], button[class*='login'], button[class*='sign']"},
            {"type": "wait", "milliseconds": 8000},
            {"type": "screenshot"},
        ],
    }
    data = firecrawl_request(payload, "2 — Login with generic selectors")
    if data:
        save_screenshot(data, "02_after_login_attempt.png")
    return data


def test_3_try_alt_urls():
    """Try alternative Expedia Partner Central URLs."""
    alt_urls = [
        "https://www.expediapartnercentral.com/",
        "https://join.expediapartnercentral.com/",
        "https://apps.expedia.com/",
    ]
    results = {}
    for i, url in enumerate(alt_urls):
        payload = {
            "url": url,
            "formats": ["screenshot", "html"],
            "actions": [
                {"type": "wait", "milliseconds": 3000},
                {"type": "screenshot"},
            ],
        }
        data = firecrawl_request(payload, f"3.{i+1} — Alt URL: {url}")
        if data:
            save_screenshot(data, f"03_{i+1}_alt_url.png")
        results[url] = data
    return results


def test_4_login_and_navigate():
    """Full flow: login then navigate to Revenue Management."""
    payload = {
        "url": "https://apps.expediapartnercentral.com/",
        "formats": ["extract", "screenshot"],
        "actions": [
            {"type": "wait", "milliseconds": 3000},
            # Fill email
            {"type": "click", "selector": "input[type='email'], input[name='email'], input[id*='email'], input[id*='user'], input[name*='user'], input[type='text']"},
            {"type": "write", "text": USERNAME},
            {"type": "wait", "milliseconds": 500},
            # Fill password
            {"type": "click", "selector": "input[type='password'], input[name='password'], input[id*='password']"},
            {"type": "write", "text": PASSWORD},
            {"type": "wait", "milliseconds": 500},
            # Submit
            {"type": "click", "selector": "button[type='submit'], input[type='submit'], button[class*='login'], button[class*='sign']"},
            {"type": "wait", "milliseconds": 10000},
            {"type": "screenshot"},
            # Try navigating to revenue management
            {"type": "click", "selector": "a[href*='revenue'], a[href*='rate'], a[href*='pricing'], [data-testid*='revenue'], [aria-label*='Revenue']"},
            {"type": "wait", "milliseconds": 5000},
            {"type": "screenshot"},
        ],
        "extract": {
            "schema": {
                "type": "object",
                "properties": {
                    "page_title": {"type": "string"},
                    "current_url": {"type": "string"},
                    "logged_in": {"type": "boolean"},
                    "navigation_items": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "competitor_rates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "competitor_name": {"type": "string"},
                                "rate": {"type": "string"},
                                "date": {"type": "string"},
                            },
                        },
                    },
                    "rate_data": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "date": {"type": "string"},
                                "your_rate": {"type": "string"},
                                "competitor_rate": {"type": "string"},
                                "hotel_name": {"type": "string"},
                            },
                        },
                    },
                    "error_messages": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            "prompt": "Extract any visible data from this page. Look for: the page title, whether the user is logged in, navigation menu items, any competitor hotel rates or rate shop data, any error messages. If this is a rate shop or revenue management page, extract all competitor rates with hotel names, dates, and prices.",
        },
    }
    data = firecrawl_request(payload, "4 — Full login + navigate to Revenue Management")
    if data:
        save_screenshot(data, "04_revenue_management.png")
    return data


def main():
    print(f"Firecrawl Expedia Partner Central Test")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"API Key: {API_KEY[:10]}...{API_KEY[-4:]}" if API_KEY else "API Key: NOT FOUND")
    print(f"Screenshots dir: {SCREENSHOTS_DIR}")

    if not API_KEY:
        print("\nERROR: FIRECRAWL_API_KEY not found in .env")
        sys.exit(1)

    # Test 1: Just see the login page
    result1 = test_1_screenshot_login_page()

    # Test 2: Try to login with generic selectors
    result2 = test_2_try_login_generic_selectors()

    # Test 3: Try alt URLs (only if test 1 didn't look right)
    # Skipping by default to save API calls — uncomment if needed
    # result3 = test_3_try_alt_urls()

    # Test 4: Full login + navigate flow
    result4 = test_4_login_and_navigate()

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Test 1 (screenshot login): {'OK' if result1 and result1.get('success') else 'FAILED'}")
    print(f"Test 2 (generic login):    {'OK' if result2 and result2.get('success') else 'FAILED'}")
    print(f"Test 4 (full flow):        {'OK' if result4 and result4.get('success') else 'FAILED'}")
    print(f"\nScreenshots saved to: {SCREENSHOTS_DIR}")


if __name__ == "__main__":
    main()
