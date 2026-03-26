#!/usr/bin/env python3
"""
EPC Rate Collector — Scrapes competitor rate shop from Expedia Partner Central.

Uses a saved Playwright session (data/epc_session.json) to access the Rev+ page.
Extracts the full competitive rate grid, our rates, and local events.

Requires: run setup_epc_session.py once first.

Usage:
  python3 collect_epc_rates.py              # Print structured data as JSON
  python3 collect_epc_rates.py --debug      # Also save screenshot + raw rows
"""

import json
import asyncio
import argparse
import re
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from playwright.async_api import async_playwright

SD_TZ = ZoneInfo("America/Los_Angeles")
SESSION_FILE = Path(__file__).parent / "data" / "epc_session.json"
DEBUG_DIR = Path(__file__).parent / "data" / "epc_debug"
HTID = "9303562"
REVPLUS_URL = f"https://apps.expediapartnercentral.com/lodging/revplus?htid={HTID}"


async def load_session(context):
    if not SESSION_FILE.exists():
        raise FileNotFoundError(
            f"No session file found at {SESSION_FILE}\n"
            "Run setup_epc_session.py first."
        )
    session = json.loads(SESSION_FILE.read_text())
    await context.add_cookies(session["cookies"])


def parse_rate_value(cell_text):
    """Convert a cell string to int rate, 'min_stay', 0 (sold out), or None."""
    text = cell_text.strip()
    if not text or text in ("—", ""):
        return None
    if "Sold out" in text:
        return 0
    if "Min." in text or "Minimum length" in text:
        return "min_stay"
    m = re.match(r"^(\d{2,4})\(?", text)
    if m:
        val = int(m.group(1))
        return val if val > 50 else None
    return None


async def scrape_epc(debug=False):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        await load_session(context)
        page = await context.new_page()

        await page.goto(REVPLUS_URL, wait_until="load", timeout=60000)
        await page.wait_for_timeout(5000)

        if "logon" in page.url.lower() or "accounts.expedia" in page.url.lower():
            raise RuntimeError("Session expired — run setup_epc_session.py again.")

        # Extract rate grid rows via role='row' (gives clean 1-name + N-data structure)
        rows = await page.evaluate("""() => {
            const result = [];
            document.querySelectorAll("tr, [role='row']").forEach(row => {
                const cells = row.querySelectorAll("td, th, [role='cell'], [role='gridcell']");
                if (cells.length > 2) {
                    result.push(Array.from(cells).map(c => c.innerText.trim()));
                }
            });
            return result;
        }""")

        # Extract events section from page text
        events_text = await page.evaluate("""() => {
            const clone = document.body.cloneNode(true);
            clone.querySelectorAll('script, style, svg').forEach(e => e.remove());
            const text = clone.innerText;
            const idx = text.lastIndexOf('Events on');
            return idx !== -1 ? text.substring(idx, idx + 5000) : '';
        }""")

        if debug:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(SD_TZ).strftime("%H%M%S")
            await page.screenshot(path=str(DEBUG_DIR / f"{ts}_revplus.png"), full_page=False)
            (DEBUG_DIR / f"{ts}_rows.json").write_text(json.dumps(rows, indent=2))

        await browser.close()

    return parse_rows(rows, events_text)


def parse_rows(rows, events_text=""):
    now = datetime.now(SD_TZ)
    today = now.date()

    result = {
        "timestamp": now.isoformat(),
        "source": "Expedia Partner Central (Rev+)",
        "our_hotel": {},
        "comp_set_avg": {},
        "competitors": {},
        "events": [],
    }

    dates = []

    comp_map = {
        "Best Western Inn & Suites San Diego": "Best Western",
        "Candlewood Suites San Diego": "Candlewood Suites",
        "Courtyard by Marriott San Diego Mission Valley": "Courtyard",
        "DoubleTree by Hilton San Diego": "DoubleTree",
        "Fairfield Inn & Suites San Diego Old Town": "Fairfield Inn",
        "Hampton Inn San Diego/Mission Valley": "Hampton Inn",
        "Hilton Garden Inn San Diego Old Town": "Hilton Garden Inn",
        "Holiday Inn Express San Diego - SeaWorld Area": "HIE SeaWorld",
        "Holiday Inn Express San Diego Airport - Old Town": "HIE Old Town",
        "Holiday Inn Express San Diego Downtown": "HIE Downtown",
        "Legacy Resort Hotel & Spa": "Legacy Resort",
    }

    for row in rows:
        if not row:
            continue
        first_cell = row[0].strip()
        data_cells = row[1:]  # everything after the first label cell
        n = len(dates)

        # ── Date header row ───────────────────────────────────────────────────
        # Format: ['MARCH 2026', 'Wed\n25', 'Thu\n26', ...]
        if (
            re.match(r"^[A-Z]+ \d{4}$", first_cell)
            and data_cells
            and re.match(r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s*\d{1,2}", data_cells[0])
            and not dates
        ):
            for cell in data_cells:
                m = re.match(r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s*(\d{1,2})", cell)
                if m:
                    day_abbr, day_num = m.group(1), int(m.group(2))
                    candidate = today
                    for _ in range(40):
                        if candidate.day == day_num and candidate.strftime("%a")[:3] == day_abbr:
                            break
                        candidate += timedelta(days=1)
                    dates.append(candidate.isoformat())
            continue

        if not dates:
            continue

        # ── Our hotel row ─────────────────────────────────────────────────────
        if "Holiday Inn Express & Suites San Diego - Mission Valley" in first_cell:
            result["our_hotel"] = {
                dates[i]: parse_rate_value(v)
                for i, v in enumerate(data_cells[:n])
            }
            continue

        # ── Competitive set average row ───────────────────────────────────────
        if "Competitive set average rates" in first_cell:
            avg = {}
            for i, cell in enumerate(data_cells[:n]):
                m = re.match(r"^(\d{2,4})\(", cell.strip())
                if m:
                    avg[dates[i]] = int(m.group(1))
            result["comp_set_avg"] = avg
            continue

        # ── Individual competitor rows ─────────────────────────────────────────
        for full_name, short_name in comp_map.items():
            if full_name in first_cell:
                result["competitors"][short_name] = {
                    dates[i]: parse_rate_value(v)
                    for i, v in enumerate(data_cells[:n])
                }
                break

    # ── Extract events ────────────────────────────────────────────────────────
    if events_text:
        blocks = re.findall(
            r"(Sports|Expos|Concerts|Conferences|Other)\s*([^\n]+?)\s*Dates?\s*([^\n]+?)\s*Predicted attendees\s*([\d,]+)",
            events_text,
        )
        for category, name, event_dates, attendees in blocks:
            result["events"].append({
                "category": category.strip(),
                "name": name.strip(),
                "dates": event_dates.strip(),
                "attendees": int(attendees.replace(",", "")),
            })

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    data = asyncio.run(scrape_epc(debug=args.debug))
    print(json.dumps(data, indent=2, default=str))


if __name__ == "__main__":
    main()
