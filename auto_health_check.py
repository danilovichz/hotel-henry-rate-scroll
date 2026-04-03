#!/usr/bin/env python3
"""
Auto Health Check — Standalone system monitor for Henry.

Runs health_check.py, interprets results with simple rules,
posts alerts or daily brief to Discord via webhook.
No Claude / Henry AI dependency required.

Runs every 30 min via launchd (com.henry.autocheck).
At 7:00-7:29am SD it automatically posts the full daily brief.
All other times: silent unless a critical issue is detected.

Usage:
    python3 auto_health_check.py           # Critical issues only (or daily if 7am window)
    python3 auto_health_check.py --daily   # Force full daily brief
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SD_TZ       = ZoneInfo('America/Los_Angeles')
SCRIPTS_DIR = Path(__file__).parent
ENV_PATH    = Path('/Users/rentamac/dani/aios/.env')
CHANNEL_ID  = '1485316410161893528'


# ─── Load env ─────────────────────────────────────────────────────────────────

def load_env() -> str:
    """Load HENRY_DISCORD_WEBHOOK from ~/dani/aios/.env."""
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line.startswith('HENRY_DISCORD_WEBHOOK='):
                return line.split('=', 1)[1].strip()
    return os.getenv('HENRY_DISCORD_WEBHOOK', '')


# ─── Discord posting ───────────────────────────────────────────────────────────

def post_to_discord(webhook_url: str, message: str) -> int | None:
    """Post a message to Discord via webhook. Returns HTTP status or None on error."""
    import urllib.request
    payload = json.dumps({
        'content': message,
        'allowed_mentions': {'parse': []},
    }).encode()
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except Exception as e:
        print(f'Discord post failed: {e}', file=sys.stderr)
        return None


# ─── Run health check ─────────────────────────────────────────────────────────

def run_health_check() -> dict:
    """Run health_check.py and return parsed JSON."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / 'health_check.py')],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        return {'error': result.stderr or 'health_check.py failed with no output'}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        return {'error': f'JSON parse failed: {e}. Raw: {result.stdout[:200]}'}


# ─── Interpret results ────────────────────────────────────────────────────────

def get_critical_issues(data: dict) -> list[str]:
    """Return list of critical issue strings. Empty list = all clear."""
    issues = []
    sys_health = data.get('system_health', {})
    dq = data.get('data_quality', {})

    # henry_bot down
    if not sys_health.get('henry_bot_running'):
        issues.append(
            '🔴 **henry_bot.py is DOWN** — scraping has stopped.\n'
            '   Fix: `launchctl kickstart gui/501/com.henry.bot` via SSH'
        )

    # Henry AI down
    if not sys_health.get('henry_ai_running'):
        issues.append(
            '🔴 **Henry AI is DOWN** — not reading Discord.\n'
            '   Fix: `launchctl kickstart gui/501/com.henry.claude-channels` via SSH\n'
            '   Note: launchd should auto-restart it — if this alert keeps firing, SSH and check logs.'
        )

    # EPC session expired
    epc = sys_health.get('epc_session_status')
    age = sys_health.get('epc_session_age_days')
    if epc == 'likely_expired':
        issues.append(
            f'🔴 **EPC session expired** ({age} days old) — forward rate data will fail.\n'
            '   Fix: Open DeskIn → Mac Mini → run `python3 setup_epc_session.py` → log in with MFA'
        )

    # Data quality flags
    for flag in dq.get('flags', []):
        issues.append(f'🔴 **Data quality:** {flag}')

    # 7-day pattern flags
    for flag in data.get('patterns_7d', {}).get('flags', []):
        issues.append(f'⚠️ **Pattern:** {flag}')

    return issues


def build_daily_brief(data: dict, now: datetime) -> str:
    """Build the full daily brief message string."""
    date_str = now.strftime('%A, %B %-d')
    sys_h    = data.get('system_health', {})
    scrape   = data.get('scrape_24h', {})
    patterns = data.get('patterns_7d', {})
    dq       = data.get('data_quality', {})
    log_s    = data.get('log_scan', {})

    lines = [f'🏨 **Henry Auto Brief** — {date_str}', '']

    # Scrape health
    runs       = scrape.get('total_runs', 0)
    expected   = scrape.get('expected_runs', 37)
    completion = scrape.get('completion_pct', 0)
    icon = '✅' if completion >= 90 else ('⚠️' if completion >= 70 else '🔴')
    lines.append('**📊 Scrape Health (last 24h)**')
    lines.append(f'{icon} {runs}/{expected} runs completed ({completion}%)')

    # Data quality
    dq_flags = dq.get('flags', [])
    if dq_flags:
        for f in dq_flags:
            lines.append(f'🔴 {f}')
    else:
        lines.append('✅ Data quality clean')

    lines.append('')

    # Rate position
    our_avg  = patterns.get('our_avg_rate_7d')
    comp_avg = patterns.get('comp_avg_rate_7d')
    gap      = patterns.get('rate_gap_pct')
    lines.append('**💰 Rate Position (7-day avg)**')
    if our_avg and comp_avg:
        gap_str = f'{gap:+.1f}%' if gap is not None else 'N/A'
        lines.append(f'Our avg: ${our_avg:.0f} | Comp avg: ${comp_avg:.0f} | Position: {gap_str}')
    else:
        lines.append('No rate data available')

    lines.append('')

    # System status
    bot_icon = '✅' if sys_h.get('henry_bot_running') else '🔴'
    ai_icon  = '✅' if sys_h.get('henry_ai_running') else '🔴'
    epc_map  = {'ok': '✅', 'refresh_soon': '⚠️', 'likely_expired': '🔴', 'missing': '🔴'}
    epc_icon = epc_map.get(sys_h.get('epc_session_status', 'missing'), '❓')
    epc_age  = sys_h.get('epc_session_age_days')
    epc_str  = f'{epc_age}d old' if epc_age is not None else 'missing'

    lines.append('**🔧 System Status**')
    lines.append(f'{bot_icon} henry_bot: {"running" if sys_h.get("henry_bot_running") else "DOWN"}')
    lines.append(f'{ai_icon} Henry AI: {"running" if sys_h.get("henry_ai_running") else "DOWN"}')
    lines.append(f'{epc_icon} EPC session: {epc_str}')

    # 7-day pattern flags
    flags = patterns.get('flags', [])
    if flags:
        lines.append('')
        lines.append('**🔍 7-Day Patterns**')
        for f in flags:
            lines.append(f'⚠️ {f}')

    # Recent errors
    errors = log_s.get('recent_errors', [])
    if errors:
        lines.append('')
        lines.append('**⚡ Recent Errors**')
        for e in errors[-3:]:
            lines.append(f'`{e[:100]}`')

    lines.append('')
    lines.append('_Auto brief — rule-based, no Claude required_')

    return '\n'.join(lines)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Henry Auto Health Check')
    parser.add_argument('--daily', action='store_true', help='Force full daily brief')
    args = parser.parse_args()

    webhook = load_env()
    if not webhook:
        print('ERROR: HENRY_DISCORD_WEBHOOK not found in env', file=sys.stderr)
        sys.exit(1)

    now = datetime.now(SD_TZ)

    # Auto-detect 7am daily brief window (7:00–7:29 AM SD)
    is_daily = args.daily or (now.hour == 7 and now.minute < 30)

    data = run_health_check()

    if 'error' in data:
        post_to_discord(webhook, f'🔴 **Auto health check failed:** {data["error"]}')
        sys.exit(1)

    if is_daily:
        message = build_daily_brief(data, now)
        post_to_discord(webhook, message)
        print(f'[{now.strftime("%H:%M")} SD] Daily brief posted')
    else:
        issues = get_critical_issues(data)
        if issues:
            header = f'🚨 **Henry Alert** — {now.strftime("%I:%M %p")} SD\n'
            message = header + '\n'.join(issues)
            post_to_discord(webhook, message)
            print(f'[{now.strftime("%H:%M")} SD] Alert posted: {len(issues)} issue(s)')
        else:
            print(f'[{now.strftime("%H:%M")} SD] All clear — no alert posted')


if __name__ == '__main__':
    main()
