#!/usr/bin/env python3
"""
Henry Health Check — Daily 24h system data gatherer.

Reads scrape CSVs, checks running processes, checks EPC session age,
scans logs, and detects 7-day patterns. Returns structured JSON for
Henry AI to analyze and post the daily brief.

Usage:
    python3 health_check.py          # Full health check (JSON to stdout)
    python3 health_check.py --pretty # Pretty-printed JSON
"""

import csv
import json
import subprocess
import sys
import argparse
from datetime import datetime, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo

SD_TZ        = ZoneInfo('America/Los_Angeles')
SCRIPTS_DIR  = Path(__file__).parent
DATA_DIR     = SCRIPTS_DIR / 'data'
LOGS_DIR     = SCRIPTS_DIR / 'logs'
HENRY_LOGS   = Path('/Users/rentamac/henry/logs')
EPC_SESSION  = DATA_DIR / 'epc_session.json'
BOT_LOG      = LOGS_DIR / 'launchd_err.log'
SCREEN_LOG   = HENRY_LOGS / 'screenlog.0'

# Expected scrape runs during operating hours (8am–2:30am = 18.5h = ~37 runs)
EXPECTED_RUNS_PER_DAY = 37


# ─── A. Scrape run analysis ────────────────────────────────────────────────────

def analyze_scrape_runs(target_date: date) -> dict:
    """Parse today's CSV and return scrape health metrics."""
    csv_path = DATA_DIR / f'rate_scroll_{target_date.strftime("%Y-%m-%d")}.csv'

    if not csv_path.exists():
        return {
            'status': 'no_data',
            'note': f'No CSV found for {target_date} — scraping may not have run yet today.',
            'total_runs': 0,
            'expected_runs': EXPECTED_RUNS_PER_DAY,
            'first_run': None,
            'last_run': None,
            'hotels': {},
        }

    rows = []
    try:
        with open(csv_path, newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        return {'status': 'error', 'note': str(e), 'hotels': {}}

    if not rows:
        return {'status': 'empty', 'note': 'CSV exists but has no data rows.', 'hotels': {}}

    # Group by run_timestamp
    runs = sorted(set(r['run_timestamp'] for r in rows))

    # Per-hotel stats
    hotels = {}
    for row in rows:
        name = row['hotel_name']
        if name not in hotels:
            hotels[name] = {
                'runs': 0,
                'errors': 0,
                'sold_out': 0,
                'suspicious_sold_out': 0,
                'latest_expedia': None,
                'latest_ihg': None,
            }
        h = hotels[name]
        h['runs'] += 1
        if row.get('error', '').strip():
            h['errors'] += 1
        if row.get('is_sold_out', '').strip().lower() == 'true':
            h['sold_out'] += 1
            # Suspicious: sold out on Expedia but IHG has a real rate
            ihg = row.get('ihg_rate_usd', '').strip()
            if ihg and ihg not in ('SOLD', 'X', '', 'None'):
                h['suspicious_sold_out'] += 1

    # Latest run rates (last run_timestamp)
    last_ts = runs[-1] if runs else None
    if last_ts:
        last_rows = [r for r in rows if r['run_timestamp'] == last_ts]
        for row in last_rows:
            name = row['hotel_name']
            if name in hotels:
                exp = row.get('lowest_rate_usd', '').strip()
                ihg = row.get('ihg_rate_usd', '').strip()
                hotels[name]['latest_expedia'] = _parse_rate(exp)
                hotels[name]['latest_ihg'] = ihg if ihg else None

    return {
        'status': 'ok',
        'total_runs': len(runs),
        'expected_runs': EXPECTED_RUNS_PER_DAY,
        'completion_pct': round(len(runs) / EXPECTED_RUNS_PER_DAY * 100, 1),
        'first_run': runs[0] if runs else None,
        'last_run': runs[-1] if runs else None,
        'hotels': hotels,
    }


def _parse_rate(val: str):
    """Convert rate string to float or None."""
    try:
        v = float(val)
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


# ─── B. System health ─────────────────────────────────────────────────────────

def check_system_health() -> dict:
    """Check running processes, screen session, and EPC session age."""

    # henry_bot.py running?
    bot_result = subprocess.run(
        ['pgrep', '-f', 'henry_bot.py'],
        capture_output=True, text=True
    )
    henry_bot_running = bool(bot_result.stdout.strip())

    # Henry AI (Claude Code with channels) running?
    ai_result = subprocess.run(
        ['pgrep', '-f', 'claude.*channels'],
        capture_output=True, text=True
    )
    henry_ai_running = bool(ai_result.stdout.strip())

    # Screen session alive?
    screen_result = subprocess.run(
        ['screen', '-ls'],
        capture_output=True, text=True
    )
    screen_alive = 'henry-ai' in screen_result.stdout

    # EPC session age
    epc_age_days = None
    epc_status = 'missing'
    if EPC_SESSION.exists():
        mtime = EPC_SESSION.stat().st_mtime
        now_ts = datetime.now(SD_TZ).timestamp()
        epc_age_days = round((now_ts - mtime) / 86400, 1)
        if epc_age_days < 5:
            epc_status = 'ok'
        elif epc_age_days < 7:
            epc_status = 'refresh_soon'
        else:
            epc_status = 'likely_expired'

    return {
        'henry_bot_running': henry_bot_running,
        'henry_ai_running': henry_ai_running,
        'screen_session_alive': screen_alive,
        'epc_session_age_days': epc_age_days,
        'epc_session_status': epc_status,
    }


# ─── C. 7-day pattern detection ───────────────────────────────────────────────

def analyze_patterns_7d(today: date) -> dict:
    """Read last 7 days of CSVs and detect systematic issues."""
    hotel_stats = {}
    our_rates   = []
    comp_rates  = []

    for offset in range(7):
        d = today - timedelta(days=offset)
        csv_path = DATA_DIR / f'rate_scroll_{d.strftime("%Y-%m-%d")}.csv'
        if not csv_path.exists():
            continue
        try:
            with open(csv_path, newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row['hotel_name']
                    if name not in hotel_stats:
                        hotel_stats[name] = {'total_rows': 0, 'errors': 0, 'sold_out': 0, 'rates': []}
                    h = hotel_stats[name]
                    h['total_rows'] += 1
                    if row.get('error', '').strip():
                        h['errors'] += 1
                    if row.get('is_sold_out', '').strip().lower() == 'true':
                        h['sold_out'] += 1
                    exp = _parse_rate(row.get('lowest_rate_usd', ''))
                    if exp:
                        h['rates'].append(exp)
                        if row.get('is_ours', '').strip().lower() == 'true':
                            our_rates.append(exp)
                        else:
                            comp_rates.append(exp)
        except Exception:
            continue

    # Summarize
    hotel_summary = {}
    flagged = []
    for name, h in hotel_stats.items():
        if h['total_rows'] == 0:
            continue
        err_pct  = round(h['errors']  / h['total_rows'] * 100, 1)
        sold_pct = round(h['sold_out'] / h['total_rows'] * 100, 1)
        avg_rate = round(sum(h['rates']) / len(h['rates']), 0) if h['rates'] else None
        hotel_summary[name] = {
            'total_rows':        h['total_rows'],
            'error_rate_pct':    err_pct,
            'sold_out_rate_pct': sold_pct,
            'avg_expedia_rate':  avg_rate,
        }
        if err_pct > 20:
            flagged.append(f"{name}: {err_pct}% ERR rate over 7 days — systematic scraping issue")

    # Rate position
    our_avg  = round(sum(our_rates)  / len(our_rates),  0) if our_rates  else None
    comp_avg = round(sum(comp_rates) / len(comp_rates), 0) if comp_rates else None
    rate_gap = None
    if our_avg and comp_avg and comp_avg > 0:
        rate_gap = round((our_avg - comp_avg) / comp_avg * 100, 1)
        if rate_gap < -15:
            flagged.append(
                f"Our hotel avg ${our_avg} vs comp avg ${comp_avg} ({rate_gap}% gap over 7 days) — "
                "consistently below market"
            )

    return {
        'hotels':          hotel_summary,
        'our_avg_rate_7d': our_avg,
        'comp_avg_rate_7d': comp_avg,
        'rate_gap_pct':    rate_gap,
        'flags':           flagged,
    }


# ─── D. Log scan ──────────────────────────────────────────────────────────────

def scan_logs() -> dict:
    """Scan last 200 lines of bot log and tail of screen log for issues."""
    recent_errors = []
    recent_warnings = []
    rate_limit_hits = 0

    # Bot log
    if BOT_LOG.exists():
        try:
            lines = BOT_LOG.read_text(errors='ignore').splitlines()
            tail = lines[-200:]
            for line in tail:
                if '[ERROR]' in line:
                    recent_errors.append(line.strip()[:120])
                elif '[WARNING]' in line or 'DATA FLAG' in line:
                    recent_warnings.append(line.strip()[:120])
        except Exception:
            pass

    # Screen log — rate limit detection
    if SCREEN_LOG.exists():
        try:
            size = SCREEN_LOG.stat().st_size
            with open(SCREEN_LOG, 'rb') as f:
                f.seek(max(0, size - 8192))
                tail_text = f.read().decode('utf-8', errors='ignore')
            rate_limit_hits = tail_text.lower().count("you've hit your limit") + \
                              tail_text.lower().count("rate limit")
        except Exception:
            pass

    return {
        'recent_errors':   recent_errors[-10:],    # Last 10 errors
        'recent_warnings': recent_warnings[-10:],  # Last 10 warnings
        'rate_limit_hits': rate_limit_hits,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Henry Daily Health Check')
    parser.add_argument('--pretty', action='store_true', help='Pretty-print JSON output')
    args = parser.parse_args()

    now   = datetime.now(SD_TZ)
    today = now.date()

    report = {
        'generated_at': now.isoformat(),
        'date':         today.isoformat(),
        'scrape_24h':   analyze_scrape_runs(today),
        'system_health': check_system_health(),
        'patterns_7d':  analyze_patterns_7d(today),
        'log_scan':     scan_logs(),
    }

    indent = 2 if args.pretty else None
    print(json.dumps(report, indent=indent, default=str))


if __name__ == '__main__':
    main()
