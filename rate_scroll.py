#!/usr/bin/env python3
"""
Henry Rate Scroll — Automated Competitor Rate Monitoring
Hotel Henry (Holiday Inn Express & Suites San Diego Mission Valley)

Runs every 30 minutes via cron.
Writes to: Google Sheets (Tab: Rate Scroll) + local CSV backup
Alerts: Discord #henry channel when notable events occur

Usage:
  python rate_scroll.py                    # Scrape today's rates (all hotels)
  python rate_scroll.py --date 2026-04-12  # Scrape a specific check-in date
  python rate_scroll.py --test             # Hampton Inn only, print result, no output writes

Cron (every 30 min):
  */30 * * * * cd /path/to/scripts && /usr/bin/python3 rate_scroll.py >> logs/cron.log 2>&1
"""

import os
import sys
import csv
import json
import logging
import argparse
import requests
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from dotenv import load_dotenv

SD_TZ = ZoneInfo('America/Los_Angeles')  # San Diego — handles PST/PDT automatically

# ─── Config ───────────────────────────────────────────────────────────────────

load_dotenv('/Users/danizal/dani/aios/.env')  # Local dev — on Railway, env vars come from dashboard

FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')
FIRECRAWL_URL = 'https://api.firecrawl.dev/v1/scrape'

DISCORD_WEBHOOK = os.getenv('HENRY_DISCORD_WEBHOOK', '')  # Set after Discord bot setup

SCRIPT_DIR = Path(__file__).parent
LOG_DIR = SCRIPT_DIR / 'logs'
DATA_DIR = SCRIPT_DIR / 'data'
LOG_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)


# ─── Hotels ───────────────────────────────────────────────────────────────────

# Our own hotel — scraped to capture public rate for the rate scroll
OUR_HOTEL = {
    'name': 'HIE Mission Valley (Ours)',
    'slug': 'holiday-inn-express-suites-san-diego-mission-valley',
    'is_ours': True,
}

# Competitive set (5 hotels from STR STAR benchmarking)
COMP_HOTELS = [
    {'name': 'Hampton Inn',   'slug': 'hampton-inn-san-diego-mission-valley',  'is_ours': False, 'primary_comp': True},
    {'name': 'Courtyard',     'slug': 'courtyard-san-diego-mission-valley-circle', 'is_ours': False},
    {'name': 'DoubleTree',    'slug': 'doubletree-club-san-diego',              'is_ours': False},
    {'name': 'HIE SeaWorld',  'slug': 'holiday-inn-express-san-diego4',         'is_ours': False},
    {'name': 'Legacy Resort', 'slug': 'the-legacy-resort-amp-spa',              'is_ours': False},
]

ALL_HOTELS = [OUR_HOTEL] + COMP_HOTELS

# ─── Firecrawl Extraction Schema ─────────────────────────────────────────────

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "hotel_name": {
            "type": "string",
            "description": "Name of the hotel as shown on the page"
        },
        "lowest_rate_usd": {
            "type": "number",
            "description": "The lowest available nightly rate in USD. Return null if sold out or page shows no rates."
        },
        "is_sold_out": {
            "type": "boolean",
            "description": "True if the hotel is fully sold out or unavailable for these dates"
        },
        "availability_signal": {
            "type": "string",
            "enum": ["available", "limited", "sold_out", "unknown"],
            "description": (
                "Availability status. 'limited' = page shows urgency like 'only X rooms left'. "
                "'sold_out' = no rooms available. 'available' = rooms showing normally."
            )
        },
        "rooms_left": {
            "type": "number",
            "description": "Number of rooms remaining if shown (e.g. 'Only 4 rooms left'). Null if not shown."
        },
        "lowest_rate_room_type": {
            "type": "string",
            "description": "Room type corresponding to the lowest rate (e.g. 'Standard King Room', 'Queen Room')"
        }
    },
    "required": ["is_sold_out", "availability_signal"]
}


# ─── Scraping ─────────────────────────────────────────────────────────────────

def booking_url(slug: str, checkin: str, checkout: str) -> str:
    return (
        f"https://www.booking.com/hotel/us/{slug}.html"
        f"?checkin={checkin}&checkout={checkout}"
        f"&group_adults=2&no_rooms=1&selected_currency=USD"
    )


def scrape_hotel(hotel: dict, checkin: str, checkout: str) -> dict:
    """Scrape a single hotel page and extract rate data via Firecrawl LLM extraction."""
    url = booking_url(hotel['slug'], checkin, checkout)

    payload = {
        "url": url,
        "formats": ["extract"],
        "extract": {
            "schema": EXTRACT_SCHEMA,
            "prompt": (
                f"This is a Booking.com hotel listing page. "
                f"Extract the lowest available nightly rate in USD for check-in {checkin}. "
                f"If all rooms are sold out or unavailable, set is_sold_out=true and lowest_rate_usd=null. "
                f"Do not guess — only return rates that are clearly visible on the page."
            )
        }
    }

    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json"
    }

    base = {
        'hotel_name': hotel['name'],
        'slug': hotel['slug'],
        'checkin': checkin,
        'is_ours': hotel.get('is_ours', False),
        'url': url,
    }

    try:
        resp = requests.post(FIRECRAWL_URL, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        if data.get('success') and data.get('data', {}).get('extract'):
            extracted = data['data']['extract']
            return {
                **base,
                'lowest_rate_usd': extracted.get('lowest_rate_usd'),
                'is_sold_out': extracted.get('is_sold_out', False),
                'availability_signal': extracted.get('availability_signal', 'unknown'),
                'rooms_left': extracted.get('rooms_left'),
                'room_type': extracted.get('lowest_rate_room_type'),
                'error': None,
            }
        else:
            log.warning(f"No extract data for {hotel['name']}: {data.get('error', 'unknown')}")
            return {**base, 'error': 'extraction_failed', 'is_sold_out': False, 'availability_signal': 'unknown'}

    except requests.exceptions.Timeout:
        log.error(f"Timeout scraping {hotel['name']}")
        return {**base, 'error': 'timeout', 'is_sold_out': False, 'availability_signal': 'unknown'}
    except Exception as e:
        log.error(f"Failed scraping {hotel['name']}: {e}")
        return {**base, 'error': str(e), 'is_sold_out': False, 'availability_signal': 'unknown'}


# ─── Rate Scroll Run ──────────────────────────────────────────────────────────

def run_rate_scroll(checkin_date: date, hotels: list = None) -> list:
    """Scrape all hotels for a given check-in date. Returns list of result dicts."""
    if hotels is None:
        hotels = ALL_HOTELS

    checkin = checkin_date.strftime('%Y-%m-%d')
    checkout = (checkin_date + timedelta(days=1)).strftime('%Y-%m-%d')

    log.info(f"Rate scroll — Check-in: {checkin} | Hotels: {len(hotels)}")

    results = []
    for hotel in hotels:
        log.info(f"  Scraping {hotel['name']}...")
        result = scrape_hotel(hotel, checkin, checkout)
        results.append(result)

        if result.get('error'):
            log.info(f"  → {hotel['name']}: ERROR — {result['error']}")
        elif result.get('is_sold_out'):
            log.info(f"  → {hotel['name']}: SOLD OUT")
        else:
            rate = result.get('lowest_rate_usd')
            avail = result.get('availability_signal', 'unknown')
            rooms = result.get('rooms_left')
            rate_str = f"${rate}" if rate else "N/A"
            rooms_str = f" ({rooms} left)" if rooms else ""
            log.info(f"  → {hotel['name']}: {rate_str} [{avail}]{rooms_str}")

    return results


# ─── Output: CSV ──────────────────────────────────────────────────────────────

CSV_COLUMNS = [
    'run_timestamp', 'checkin',
    'hotel_name', 'is_ours',
    'lowest_rate_usd', 'is_sold_out', 'availability_signal',
    'rooms_left', 'room_type',
    'error', 'url'
]


def write_csv(results: list, run_time: datetime):
    """Append results to daily CSV. One file per day, one row per hotel per scrape run."""
    csv_path = DATA_DIR / f"rate_scroll_{run_time.strftime('%Y-%m-%d')}.csv"
    is_new = not csv_path.exists()

    with open(csv_path, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction='ignore')
        if is_new:
            writer.writeheader()
        for r in results:
            row = {**r, 'run_timestamp': run_time.strftime('%Y-%m-%d %H:%M:%S')}
            writer.writerow(row)

    log.info(f"CSV: {len(results)} rows → {csv_path.name}")


# ─── Output: Google Sheets ────────────────────────────────────────────────────

def write_sheets(results: list, run_time: datetime):
    """
    Write one row per scrape run to Google Sheets (Tab: 'Rate Scroll').

    Row format: [Timestamp | Check-in | Our Rate | Our Status | Hampton Rate | Hampton Status | ...]

    Setup required:
      1. Create a Google Sheet, name one tab 'Rate Scroll'
      2. Set up a Google service account and share the sheet with its email
      3. Set in .env:
           GOOGLE_SHEETS_CREDENTIALS=/path/to/service-account.json
           HENRY_RATE_SCROLL_SHEET_ID=<sheet ID from URL>
      4. pip install gspread google-auth
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        log.info("gspread not installed — skipping Sheets output. pip install gspread google-auth")
        return

    creds_path = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
    sheet_id = os.getenv('HENRY_RATE_SCROLL_SHEET_ID')

    if not creds_path or not sheet_id:
        log.info("Sheets not configured — skipping. Set GOOGLE_SHEETS_CREDENTIALS + HENRY_RATE_SCROLL_SHEET_ID in .env")
        return

    try:
        scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheet_id)
        ws = sh.worksheet("Rate Scroll")

        # One row per run: [Timestamp, Check-in, Our Rate, Our Status, H1 Rate, H1 Status, ...]
        row = [run_time.strftime('%Y-%m-%d %H:%M'), results[0].get('checkin', '') if results else '']

        # Our hotel first, then comps in order
        ordered = sorted(results, key=lambda r: (not r.get('is_ours', False), r.get('hotel_name', '')))
        for r in ordered:
            if r.get('is_sold_out'):
                row.extend(['SOLD OUT', 'sold_out'])
            else:
                row.extend([r.get('lowest_rate_usd', ''), r.get('availability_signal', '')])

        ws.append_row(row, value_input_option='USER_ENTERED')
        log.info(f"Sheets: row written — {run_time.strftime('%H:%M')}")

    except Exception as e:
        log.error(f"Sheets write failed: {e}")


# ─── Output: Excel (.xlsx) ────────────────────────────────────────────────────

# Row layout matching Darshan's "Rate Shop" template exactly
XLSX_ROWS = [
    'header_date',       # Row 1: Date
    'header_time',       # Row 2: Day + time
    'rooms_left',        # Row 3: Rooms Left to sell
    'our_rate',          # Row 4: Our Express HC
    'hie_seaworld',      # Row 5: Holiday Inn Express Sea World
    'courtyard',         # Row 6: Courtyard Marriott Mission Valley
    'hampton',           # Row 7: Hampton Inn
    'doubletree',        # Row 8: DoubleTree Hotel Circle
    'legacy',            # Row 9: Legacy Resort
    'ooo',               # Row 10: Out of order (manual)
    'kings_open',        # Row 11: Kings Open (manual)
    'arrivals',          # Row 12: Arrivals (manual)
    'day_use',           # Row 13: Day Use (manual)
    'early_departures',  # Row 14: Early Departures (manual)
    'hurdle_points',     # Row 15: Hurdle Points (manual)
    'declines',          # Row 16: Declines (manual)
    'front_desk',        # Row 17: Front Desk (manual)
]

# Map hotel names to xlsx row keys
HOTEL_TO_ROW = {
    'HIE Mission Valley (Ours)': 'our_rate',
    'HIE SeaWorld':              'hie_seaworld',
    'Courtyard':                 'courtyard',
    'Hampton Inn':               'hampton',
    'DoubleTree':                'doubletree',
    'Legacy Resort':             'legacy',
}


def write_xlsx(results: list, run_time: datetime, checkin_date):
    """
    Write/update daily Excel file matching Darshan's Rate Shop format.
    One file per day, each scrape run adds a new column.
    """
    try:
        from openpyxl import Workbook, load_workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        log.info("openpyxl not installed — skipping xlsx output. pip install openpyxl")
        return

    xlsx_path = DATA_DIR / f"Rate_Shop_{checkin_date.strftime('%Y-%m-%d')}.xlsx"
    day_name = checkin_date.strftime('%A')
    time_str = run_time.strftime('%I:%M %p').lstrip('0')

    # Row labels (column A)
    row_labels = {
        1: checkin_date.strftime('%m/%d/%Y'),
        2: f'DAY: {day_name}',
        3: 'Rooms Left to sell',
        4: 'Our Express HC',
        5: 'Holiday Inn Express Sea World',
        6: 'Courtyard Marriott Mission Valley',
        7: 'Hampton Inn Mission Valley',
        8: 'DoubleTree Hotel Circle',
        9: 'Legacy Resort Hotel & Spa',
        10: 'Out of order',
        11: 'Kings Open',
        12: 'Arrivals',
        13: 'Day Use',
        14: 'Early Departures',
        15: 'Hurdle Points',
        16: 'Declines',
        17: 'Front Desk',
    }

    # Hotel name → row number
    hotel_row_map = {
        'HIE Mission Valley (Ours)': 4,
        'HIE SeaWorld': 5,
        'Courtyard': 6,
        'Hampton Inn': 7,
        'DoubleTree': 8,
        'Legacy Resort': 9,
    }

    # Load or create workbook
    if xlsx_path.exists():
        wb = load_workbook(xlsx_path)
        ws = wb.active
        # Find next empty column
        col = ws.max_column + 1
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = 'Rate Shop'
        col = 2  # Column B is first data column

        # Write row labels in column A
        ws.column_dimensions['A'].width = 35
        for row_num, label in row_labels.items():
            cell = ws.cell(row=row_num, column=1, value=label)
            cell.font = Font(bold=True, name='Arial', size=10)
            cell.alignment = Alignment(vertical='center')

    # Styling
    header_fill = PatternFill('solid', fgColor='4472C4')
    header_font = Font(bold=True, color='FFFFFF', name='Arial', size=10)
    data_font = Font(name='Arial', size=10)
    sold_out_fill = PatternFill('solid', fgColor='FF6B6B')
    sold_out_font = Font(bold=True, color='FFFFFF', name='Arial', size=10)
    available_fill = PatternFill('solid', fgColor='C6EFCE')
    limited_fill = PatternFill('solid', fgColor='FFEB9C')
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9'),
    )

    # Write header row (time)
    ws.cell(row=1, column=col, value=checkin_date.strftime('%m/%d')).font = header_font
    ws.cell(row=1, column=col).fill = header_fill
    ws.cell(row=1, column=col).alignment = Alignment(horizontal='center')

    ws.cell(row=2, column=col, value=time_str).font = header_font
    ws.cell(row=2, column=col).fill = header_fill
    ws.cell(row=2, column=col).alignment = Alignment(horizontal='center')

    # Set column width
    from openpyxl.utils import get_column_letter
    ws.column_dimensions[get_column_letter(col)].width = 14

    # Write rate data
    our_rooms_left = None
    for r in results:
        hotel_name = r.get('hotel_name', '')
        row_num = hotel_row_map.get(hotel_name)
        if not row_num:
            continue

        cell = ws.cell(row=row_num, column=col)
        cell.border = thin_border
        cell.alignment = Alignment(horizontal='center')

        if r.get('is_sold_out'):
            cell.value = 'X'
            cell.fill = sold_out_fill
            cell.font = sold_out_font
        elif r.get('lowest_rate_usd'):
            cell.value = r['lowest_rate_usd']
            cell.font = data_font
            cell.number_format = '$#,##0'
            # Color based on availability
            avail = r.get('availability_signal', '')
            if avail == 'limited':
                cell.fill = limited_fill
            elif avail == 'available':
                cell.fill = available_fill
        else:
            cell.value = 'N/A'
            cell.font = data_font

        # Capture our rooms left
        if r.get('is_ours') and r.get('rooms_left'):
            our_rooms_left = r['rooms_left']

    # Write rooms left (Row 3) — from our hotel's scrape data
    rooms_cell = ws.cell(row=3, column=col)
    rooms_cell.border = thin_border
    rooms_cell.alignment = Alignment(horizontal='center')
    rooms_cell.font = Font(bold=True, name='Arial', size=11)
    if our_rooms_left is not None:
        rooms_cell.value = our_rooms_left
        if our_rooms_left <= 5:
            rooms_cell.fill = PatternFill('solid', fgColor='FF6B6B')
            rooms_cell.font = Font(bold=True, color='FFFFFF', name='Arial', size=11)
        elif our_rooms_left <= 15:
            rooms_cell.fill = limited_fill
        else:
            rooms_cell.fill = available_fill

    # Manual rows (10-17) — leave empty for Darshan to fill
    for row_num in range(10, 18):
        cell = ws.cell(row=row_num, column=col)
        cell.border = thin_border
        cell.alignment = Alignment(horizontal='center')
        cell.font = data_font

    wb.save(xlsx_path)
    log.info(f"XLSX: column added → {xlsx_path.name}")


# ─── Alerts: Discord ──────────────────────────────────────────────────────────

def load_previous_results(today: str) -> dict:
    """Load the second-to-last scrape run from today's CSV for change detection."""
    csv_path = DATA_DIR / f"rate_scroll_{today}.csv"
    if not csv_path.exists():
        return {}

    rows = []
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return {}

    # Group rows by run_timestamp, get the penultimate batch
    seen_timestamps = []
    grouped = {}
    for r in rows:
        ts = r['run_timestamp']
        if ts not in grouped:
            grouped[ts] = []
            seen_timestamps.append(ts)
        grouped[ts].append(r)

    if len(seen_timestamps) < 2:
        return {}  # Only one run so far, no previous to compare

    prev_batch = grouped[seen_timestamps[-2]]
    return {r['hotel_name']: r for r in prev_batch}


def check_alerts(results: list, prev_results: dict) -> list:
    """Compare current scrape to previous run and return alert messages."""
    alerts = []

    our_rate = None
    for r in results:
        if r.get('is_ours') and r.get('lowest_rate_usd'):
            our_rate = r['lowest_rate_usd']
            break

    for r in results:
        name = r.get('hotel_name', '')
        rate = r.get('lowest_rate_usd')
        is_sold_out = r.get('is_sold_out', False)
        is_ours = r.get('is_ours', False)

        prev = prev_results.get(name, {})
        prev_rate_raw = prev.get('lowest_rate_usd', '')
        prev_rate = float(prev_rate_raw) if prev_rate_raw else None
        prev_sold_out = prev.get('is_sold_out', 'False') == 'True'

        # Comp just went sold out
        if is_sold_out and not prev_sold_out and not is_ours:
            alerts.append(f"🔴 **{name}** just went SOLD OUT. We have inventory — raise rate?")

        # Comp came back from sold out (they released rooms or cancelled)
        if not is_sold_out and prev_sold_out and not is_ours:
            alerts.append(f"🟡 **{name}** back in inventory at ${rate}. Monitor.")

        # Comp dropped rate significantly
        if rate and prev_rate and not is_ours:
            drop = prev_rate - rate
            if drop >= 15:
                alerts.append(
                    f"⚠️ **{name}** dropped ${drop:.0f} (${prev_rate:.0f} → ${rate:.0f}). "
                    f"We're at ${our_rate or '?'}. Respond?"
                )

        # Comp is pricing much higher than us (revenue opportunity)
        if rate and our_rate and not is_ours and not is_sold_out:
            gap = rate - our_rate
            if gap >= 30:
                alerts.append(
                    f"💡 **{name}** is ${gap:.0f} above us (${rate:.0f} vs our ${our_rate:.0f}). "
                    f"Room to raise?"
                )

    return alerts


def send_discord_alert(alerts: list, run_time: datetime):
    """Send alert digest to Discord #henry channel via webhook."""
    if not alerts or not DISCORD_WEBHOOK:
        if alerts:
            log.info(f"Alerts triggered but HENRY_DISCORD_WEBHOOK not set:\n" + "\n".join(alerts))
        return

    message = f"**Henry — Rate Alert** `{run_time.strftime('%I:%M %p')}`\n\n" + "\n".join(alerts)

    try:
        resp = requests.post(DISCORD_WEBHOOK, json={"content": message}, timeout=10)
        resp.raise_for_status()
        log.info(f"Discord: {len(alerts)} alert(s) sent")
    except Exception as e:
        log.error(f"Discord alert failed: {e}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Henry Rate Scroll — Automated competitor rate monitoring")
    parser.add_argument('--date', help='Check-in date YYYY-MM-DD (default: today)')
    parser.add_argument('--test', action='store_true', help='Hampton Inn only, print results, no CSV/Sheets/alerts written')
    parser.add_argument('--no-alerts', action='store_true', help='Skip Discord alerts this run')
    args = parser.parse_args()

    if not FIRECRAWL_API_KEY:
        log.error("FIRECRAWL_API_KEY not set in .env")
        sys.exit(1)

    # Operating hours check: 8:00 AM – 2:30 AM San Diego time
    # Skip silently outside these hours (unless --test or --date override)
    if not args.test and not args.date:
        sd_now = datetime.now(SD_TZ)
        sd_hour, sd_min = sd_now.hour, sd_now.minute
        in_hours = sd_hour >= 8 or sd_hour <= 1 or (sd_hour == 2 and sd_min <= 30)
        if not in_hours:
            log.info(f"Outside operating hours ({sd_now.strftime('%I:%M %p')} SD). Skipping.")
            sys.exit(0)

    checkin_date = datetime.now(SD_TZ).date()
    if args.date:
        try:
            checkin_date = date.fromisoformat(args.date)
        except ValueError:
            log.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD.")
            sys.exit(1)

    hotels = [COMP_HOTELS[0]] if args.test else ALL_HOTELS  # Hampton only in test mode
    run_time = datetime.now(SD_TZ)

    # Run the scrape
    results = run_rate_scroll(checkin_date, hotels)

    # Print summary table
    print(f"\n{'─' * 65}")
    print(f"  Henry Rate Scroll — {run_time.strftime('%Y-%m-%d %H:%M')}  |  Check-in: {checkin_date}")
    print(f"{'─' * 65}")
    print(f"  {'Hotel':<28} {'Rate':>8}  {'Status':<12}  {'Rooms Left':>10}")
    print(f"  {'─' * 60}")
    for r in results:
        if r.get('is_sold_out'):
            rate_str = "SOLD OUT"
        elif r.get('lowest_rate_usd'):
            rate_str = f"${r['lowest_rate_usd']:.0f}"
        else:
            rate_str = "N/A" if not r.get('error') else f"ERR: {r['error'][:12]}"
        status = r.get('availability_signal', '—')
        rooms = str(r.get('rooms_left', '—') or '—')
        flag = " ◄ OURS" if r.get('is_ours') else ""
        print(f"  {r.get('hotel_name', ''):<28} {rate_str:>8}  {status:<12}  {rooms:>10}{flag}")
    print(f"{'─' * 65}\n")

    if args.test:
        log.info("Test mode — skipping CSV, Sheets, and alert writes")
        return

    # Write outputs
    write_csv(results, run_time)
    write_xlsx(results, run_time, checkin_date)
    write_sheets(results, run_time)

    # Check alerts
    if not args.no_alerts:
        prev = load_previous_results(run_time.strftime('%Y-%m-%d'))
        alerts = check_alerts(results, prev)
        if alerts:
            for a in alerts:
                log.info(f"ALERT: {a}")
            send_discord_alert(alerts, run_time)


if __name__ == '__main__':
    main()
