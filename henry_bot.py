#!/usr/bin/env python3
"""
Henry — AI Revenue Manager Discord Bot
Hotel Henry (Holiday Inn Express & Suites San Diego Mission Valley)

Commands:
  !rates              → Tonight's live comp set from latest scrape
  !rates [date]       → Rates for a specific date (e.g. !rates 2026-04-12)
  !henry [question]   → Ask Henry anything — answers using live rate data + context

Run:
  python henry_bot.py

Deploy (Railway):
  Same server as rate_scroll.py cron. Set env vars in Railway dashboard.
"""

import os
import sys
import csv
import asyncio
import logging
import requests
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from dotenv import load_dotenv

# Import write_xlsx directly so xlsx generation runs in the bot's own process
# (avoids silent openpyxl failures in subprocess)
sys.path.insert(0, str(Path(__file__).parent))
from rate_scroll import write_xlsx, write_epc_sheet, send_discord_xlsx

SD_TZ = ZoneInfo('America/Los_Angeles')  # San Diego — handles PST/PDT automatically

import discord
from discord.ext import commands, tasks

# ─── Config ───────────────────────────────────────────────────────────────────

load_dotenv('/Users/rentamac/dani/aios/.env')  # Local dev — on Railway, env vars come from dashboard

BOT_TOKEN       = os.getenv('HENRY_DISCORD_BOT_TOKEN')
OPENROUTER_KEY  = os.getenv('HENRY_OPENROUTER_API_KEY')
AI_MODEL        = 'google/gemini-3-flash-preview'  # via OpenRouter
OPENROUTER_URL  = 'https://openrouter.ai/api/v1/chat/completions'

DATA_DIR = Path(__file__).parent / 'data'

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# ─── Data Access ──────────────────────────────────────────────────────────────

def load_latest_rates(target_date: str = None) -> tuple[list[dict], bool]:
    """
    Load the most recent scrape run for a given date from CSV.
    Returns (rows, is_stale) — stale if data is older than 45 minutes.
    """
    if target_date is None:
        target_date = datetime.now(SD_TZ).date().strftime('%Y-%m-%d')

    csv_path = DATA_DIR / f'rate_scroll_{target_date}.csv'
    if not csv_path.exists():
        return [], True

    rows = []
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return [], True

    latest_ts = max(r['run_timestamp'] for r in rows)
    latest_rows = [r for r in rows if r['run_timestamp'] == latest_ts]

    # Check staleness — data older than 45 min means cron likely missed a run
    ts_dt = datetime.strptime(latest_ts, '%Y-%m-%d %H:%M:%S')
    is_stale = (datetime.now(SD_TZ).replace(tzinfo=None) - ts_dt).total_seconds() > 45 * 60

    return latest_rows, is_stale


def live_scrape_tonight() -> tuple[list[dict], Path | None]:
    """Trigger a live Firecrawl scrape. Returns (rates, xlsx_path)."""
    import subprocess, sys
    script = Path(__file__).parent / 'rate_scroll.py'
    today = datetime.now(SD_TZ).date().strftime('%Y-%m-%d')
    xlsx_path = DATA_DIR / f'Rate_Shop_{today}.xlsx'

    log.info(f"Triggering live scrape... script={script} data_dir={DATA_DIR}")
    result = subprocess.run(
        [sys.executable, str(script), '--force', '--no-xlsx'],
        capture_output=True, text=True, timeout=180
    )

    # Always log full output for debugging
    if result.stdout:
        log.info(f"Scrape stdout:\n{result.stdout[-800:]}")
    if result.stderr:
        log.info(f"Scrape stderr:\n{result.stderr[-800:]}")

    webhook = os.getenv('HENRY_DISCORD_WEBHOOK', '')
    if result.returncode != 0:
        err = (result.stderr or result.stdout or 'no output')[-400:]
        log.error(f"Scrape failed (exit {result.returncode})")
        if webhook:
            requests.post(webhook, json={"content": f"⚠️ **Scrape error** (exit {result.returncode}):\n```{err}```"}, timeout=5)
    else:
        log.info(f"Scrape OK — xlsx exists: {xlsx_path.exists()} | data_dir contents: {list(DATA_DIR.iterdir()) if DATA_DIR.exists() else 'DIR MISSING'}")

    rows, _ = load_latest_rates()

    # Write xlsx in the bot's own process — guarantees same env/packages
    if rows:
        try:
            run_time = datetime.now(SD_TZ)
            checkin = datetime.strptime(today, '%Y-%m-%d').date()
            write_xlsx(rows, run_time, checkin)
            log.info(f"xlsx written by bot process — {xlsx_path}")
            send_discord_xlsx(run_time, checkin)
            log.info("xlsx uploaded to Discord")
        except Exception as e:
            log.error(f"xlsx write/upload failed in bot process: {e}")

    return rows, xlsx_path if xlsx_path.exists() else None


def load_rate_history(target_date: str = None, max_runs: int = 10) -> list[dict]:
    """Load recent scrape history for trend context."""
    if target_date is None:
        target_date = datetime.now(SD_TZ).date().strftime('%Y-%m-%d')

    csv_path = DATA_DIR / f'rate_scroll_{target_date}.csv'
    if not csv_path.exists():
        return []

    with open(csv_path) as f:
        rows = list(csv.DictReader(f))

    # Get last N unique timestamps
    seen = []
    for r in rows:
        if r['run_timestamp'] not in seen:
            seen.append(r['run_timestamp'])
    recent_timestamps = seen[-max_runs:]

    return [r for r in rows if r['run_timestamp'] in recent_timestamps]


def format_rates_table(rates: list[dict], target_date: str = None) -> str:
    """Format rates into a clean Discord message."""
    if not rates:
        return "No rate data found. Scraper may not have run yet for this date."

    ts = rates[0].get('run_timestamp', 'unknown')
    checkin = rates[0].get('checkin', target_date or 'today')

    lines = [f"**Rate Shop** — Check-in: `{checkin}` | Updated: `{ts}`\n"]
    lines.append("```")
    lines.append(f"{'Hotel':<28} {'Expedia':>8} {'IHG':>6}  {'Status':<8} {'Kings':>5} {'Queens':>6}")
    lines.append("─" * 68)

    for r in rates:
        name = r.get('hotel_name', '')
        flag = " ◄" if r.get('is_ours') == 'True' else ""

        # Expedia rate
        if r.get('is_sold_out') == 'True':
            exp_str = "SOLD"
        elif r.get('lowest_rate_usd'):
            exp_str = f"${float(r['lowest_rate_usd']):.0f}"
        else:
            exp_str = "N/A"

        # IHG rate
        ihg_family = r.get('ihg_family', 'False')
        if ihg_family == 'True' or ihg_family is True:
            ihg_raw = r.get('ihg_rate_usd', '')
            ihg_str = f"${float(ihg_raw):.0f}" if ihg_raw else "—"
        else:
            ihg_str = "X"

        status = r.get('availability_signal', '—')[:8]
        kings = r.get('kings_available', '—') or '—'
        queens = r.get('queens_available', '—') or '—'
        lines.append(f"{name:<28} {exp_str:>8} {ihg_str:>6}  {status:<8} {str(kings):>5} {str(queens):>6}{flag}")

    lines.append("```")
    return "\n".join(lines)


def load_knowledge() -> str:
    """Load all knowledge base files from the knowledge/ directory."""
    knowledge_dir = Path(__file__).parent / 'knowledge'
    if not knowledge_dir.exists():
        return ""

    chunks = []
    for f in sorted(knowledge_dir.glob('*.md')):
        chunks.append(f.read_text())
    return "\n\n---\n\n".join(chunks)


def build_henry_context(question: str) -> str:
    """Build the full context prompt for Henry's AI response."""

    # Load today's latest rates
    today = datetime.now(SD_TZ).date().strftime('%Y-%m-%d')
    latest, _ = load_latest_rates(today)
    history = load_rate_history(today)

    # Format latest rates as structured text
    rate_lines = []
    for r in latest:
        if r.get('is_sold_out') == 'True':
            rate_str = "SOLD OUT"
        else:
            rate_str = f"${float(r['lowest_rate_usd']):.0f}" if r.get('lowest_rate_usd') else "N/A"
        ours = " (OUR HOTEL)" if r.get('is_ours') == 'True' else ""
        rooms = f", {r['rooms_left']} rooms left" if r.get('rooms_left') else ""
        kings = f", kings: {r.get('kings_available', '?')}" if r.get('kings_available') else ""
        queens = f", queens: {r.get('queens_available', '?')}" if r.get('queens_available') else ""
        ihg = f", IHG: ${float(r['ihg_rate_usd']):.0f}" if r.get('ihg_rate_usd') else ""
        rate_lines.append(f"- {r['hotel_name']}{ours}: Expedia {rate_str}{ihg} [{r.get('availability_signal', '?')}]{rooms}{kings}{queens}")

    # Summarize history for trend context
    history_summary = ""
    if history:
        timestamps = sorted(set(r['run_timestamp'] for r in history))
        history_summary = f"\nRate history today ({len(timestamps)} scrape runs from {timestamps[0]} to {timestamps[-1]})."

    latest_ts = latest[0]['run_timestamp'] if latest else "no data yet"

    # Load knowledge base
    knowledge = load_knowledge()

    context = f"""You are Henry — an AI revenue manager for Holiday Inn Express & Suites San Diego Mission Valley (Hotel Circle).

HOTEL CONTEXT:
- 104 rooms, IHG franchise, Mission Valley / Hotel Circle area
- Room types: King | King Suite (king + sofa) | Two Queen | Two Queen + sofa | King Jacuzzi (king + sofa + jacuzzi)
- Floor rate: $109 (never price below this)
- Currently ~97% average occupancy — the opportunity is ADR optimization, not filling rooms
- Annual room revenue: ~$6.32M | ADR range: $107–$353 (avg ~$170)
- Competitive set (Rate Shop): HIE SeaWorld, HIE Old Town, HIE Downtown, Courtyard Marriott Mission Valley, Hampton Inn Mission Valley
- Rate parity required across all OTAs — one rate change propagates everywhere via channel manager
- IHG franchise fee: 9% on ALL revenue regardless of channel
- Expedia cost: 15% commission + 12% IHG = 27% gone before operating costs
- Key demand drivers: Padres games, Comic-Con, conventions, military events, university graduations, cruise departures, school breaks (Arizona spring break), construction crews, traveling nurses

CRITICAL PRICING PHILOSOPHY — HERD HOTEL:
- Bobby (owner): "We are a herd of hotels that can't be front runners unless something exceptional is happening."
- Hotels move in blocks — when one raises, if 2 follow, everyone follows.
- At this tier (select-service), competitors race to the MIDDLE, not the bottom.
- Henry follows the market. Henry does NOT recommend raising rates just because one comp is higher.
- NEVER recommend raising rates when we have 20+ rooms unsold — they need to sell.
- Hold rate as long as possible on peak days, only drop if pace falls behind.
- When a comp goes sold out: HOLD rate (don't raise aggressively).
- When 2+ comps drop: follow the market down.
- When inventory is high late in the day: recommend adjusting down.

CURRENT RATE DATA (as of {latest_ts}):
{chr(10).join(rate_lines) if rate_lines else "No data available yet."}
{history_summary}

REVENUE MANAGEMENT KNOWLEDGE BASE:
{knowledge}

RESPONSE GUIDELINES:
- Respond concisely and directly. Give a clear recommendation when asked.
- Use real numbers from the data above — never invent rates or availability.
- Frame recommendations in dollar impact when possible (e.g. "+$20 × 3 rooms = $60 more tonight").
- Always specify the recommended rate as a number.
- When suggesting rate changes, recommend adjusting the PMS rack rate — it flows to all channels.
- HERD STRATEGY: Never recommend raising rate just because one comp is higher. Watch what the HERD does.
- Don't panic-match a single distressed comp. Only follow if 2+ comps are moving.
- Consider booking window: for tonight's rates, most demand has already happened. For dates 2–4 weeks out, rate changes have maximum impact.
- When we have lots of rooms unsold, the priority is SELLING, not maximizing rate.
- Event-based pricing: every 10,000 attendees ≈ +$10. Events stack. Local events (Padres) weight lower than visitor events (Comic-Con).

User question: {question}"""

    return context


def ask_henry(question: str) -> str:
    """Send question to Gemini Flash via OpenRouter with full hotel context."""
    if not OPENROUTER_KEY:
        return "⚠️ HENRY_OPENROUTER_API_KEY not set. Add it to .env."

    context = build_henry_context(question)

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": AI_MODEL,
                "messages": [{"role": "user", "content": context}],
                "max_tokens": 500,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        log.error(f"OpenRouter call failed: {e}")
        return f"⚠️ Henry couldn't respond: {e}"


# ─── Bot ──────────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)


@bot.command(name='rates')
async def cmd_rates(ctx, arg: str = None):
    """
    !rates              — tonight's rates (from last scrape, instant)
    !rates live         — force a fresh scrape right now (~70 sec)
    !rates 2026-04-12   — rates for a specific date
    """
    force_live = arg and arg.lower() == 'live'
    target_date = datetime.now(SD_TZ).date().strftime('%Y-%m-%d')

    if arg and not force_live:
        try:
            datetime.strptime(arg, '%Y-%m-%d')
            target_date = arg
        except ValueError:
            await ctx.send("❌ Use `!rates`, `!rates live`, or `!rates 2026-04-12`")
            return

    if force_live:
        await ctx.send("🔄 Scraping live data now... (~60 sec)")
        async with ctx.typing():
            rates, xlsx_path = await asyncio.to_thread(live_scrape_tonight)
        await ctx.send(format_rates_table(rates, target_date))
        if xlsx_path:
            await ctx.send(
                file=discord.File(str(xlsx_path), filename=xlsx_path.name),
                content="📊 Updated Rate Shop:"
            )
        return

    rates, is_stale = load_latest_rates(target_date)

    if is_stale and rates:
        await ctx.send("⏳ Data is stale (>45 min). Pulling fresh rates...")
        async with ctx.typing():
            rates, _ = await asyncio.to_thread(live_scrape_tonight)
    elif not rates:
        await ctx.send("⏳ No data yet for today. Pulling fresh rates...")
        async with ctx.typing():
            rates, _ = await asyncio.to_thread(live_scrape_tonight)

    await ctx.send(format_rates_table(rates, target_date))


@bot.command(name='henry')
async def cmd_henry(ctx, *, question: str = None):
    """
    !henry [question] — ask Henry anything about rates, pricing strategy, market signals
    """
    if not question:
        await ctx.send("Ask me anything. Example: `!henry should I raise my rate tonight?`")
        return

    async with ctx.typing():
        answer = ask_henry(question)

    await ctx.send(f"**Henry:** {answer}")


@bot.command(name='help')
async def cmd_help(ctx):
    help_text = """**Henry — AI Revenue Manager**

`!rates` — Tonight's full comp set (latest scrape)
`!rates live` — Force a fresh scrape right now (~60 sec)
`!rates 2026-04-12` — Rates for a specific date
`!henry [question]` — Ask Henry anything

**Example questions:**
• `!henry should I raise my rate tonight?`
• `!henry Hampton just dropped to $149, what do I do?`
• `!henry what does the comp set look like this weekend?`
• `!henry HIE SeaWorld is sold out, what should our rate be?`
• `!henry we have 20 rooms left at 7pm, what do you recommend?`"""
    await ctx.send(help_text)


# ─── Built-in Scheduler ───────────────────────────────────────────────────────

def run_epc_scrape() -> bool:
    """Pull EPC forward rates, write to today's Excel, and send to Discord. Returns True on success."""
    try:
        import asyncio as _asyncio
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent))
        from collect_epc_rates import scrape_epc
        from rate_scroll import send_discord_xlsx
        from datetime import datetime
        from zoneinfo import ZoneInfo

        epc_data = _asyncio.run(scrape_epc())
        write_epc_sheet(epc_data)

        # Send the full file (Rate Shop + EPC Forward tabs) to Discord
        now = datetime.now(ZoneInfo('America/Los_Angeles'))
        send_discord_xlsx(now, now.date())

        log.info("EPC forward rates written and sent to Discord")
        return True
    except FileNotFoundError:
        log.warning("EPC session not set up — run setup_epc_session.py to enable EPC scraping")
        return False
    except RuntimeError as e:
        if "Session expired" in str(e):
            log.warning("EPC session expired — run setup_epc_session.py to refresh")
        else:
            log.error(f"EPC scrape error: {e}")
        return False
    except Exception as e:
        log.error(f"EPC scrape failed: {e}")
        return False


# ─── Control Commands (Mac Mini only — set HENRY_CONTROL_MODE=true) ────────────
# These commands control the Henry AI (Claude Code) screen session on the Mac Mini.
# On Railway, these commands silently do nothing useful (no screen session there).

ALERT_CHANNEL_ID = int(os.getenv('HENRY_ALERT_CHANNEL', '0') or '0')
HENRY_AI_LOG = Path('/Users/rentamac/henry/logs/screenlog.0')  # screen -L default log name
HENRY_START_SCRIPT = '/Users/rentamac/henry/scripts/start-henry-ai.sh'
HENRY_LOGS_DIR = '/Users/rentamac/henry/logs'

# Auto-detect Mac Mini by checking if the Henry AI start script exists on disk.
# True on Mac Mini, False on Railway or any other host.
IS_MAC_MINI = Path(HENRY_START_SCRIPT).exists()

def _start_henry_screen():
    """Start Henry AI in a screen session with logging enabled (screen -L writes screenlog.0)."""
    import subprocess
    Path(HENRY_LOGS_DIR).mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        ['screen', '-L', '-dmS', 'henry-ai', HENRY_START_SCRIPT],
        capture_output=True, text=True,
        cwd=HENRY_LOGS_DIR  # screen writes screenlog.0 in cwd
    )

_rate_limit_alerted = False


def _henry_ai_running() -> bool:
    import subprocess
    procs = subprocess.run(['ps', 'aux'], capture_output=True, text=True).stdout
    return any('claude' in l and 'channels' in l for l in procs.splitlines())


@bot.command(name='start')
async def cmd_start(ctx, target: str = 'henry'):
    if target.lower() != 'henry':
        return
    if not IS_MAC_MINI:
        await ctx.send('Control commands only available on Mac Mini.')
        return
    result = _start_henry_screen()
    if result.returncode != 0:
        await ctx.send(f'Failed to start Henry AI: {result.stderr}')
        return
    await ctx.send('Henry AI starting...')
    for _ in range(15):
        await asyncio.sleep(2)
        if _henry_ai_running():
            await ctx.send('Henry AI is ready.')
            return
    await ctx.send('Still starting — use `!status` to check.')


@bot.command(name='stop')
async def cmd_stop(ctx, target: str = 'henry'):
    if target.lower() != 'henry':
        return
    if not IS_MAC_MINI:
        await ctx.send('Control commands only available on Mac Mini.')
        return
    import subprocess
    subprocess.run(['pkill', '-9', '-f', 'claude.*channels'], capture_output=True)
    subprocess.run(['screen', '-S', 'henry-ai', '-X', 'quit'], capture_output=True)
    await ctx.send('Henry AI stopped.')


@bot.command(name='restart')
async def cmd_restart(ctx, target: str = 'henry'):
    if target.lower() != 'henry':
        return
    if not IS_MAC_MINI:
        await ctx.send('Control commands only available on Mac Mini.')
        return
    import subprocess
    subprocess.run(['pkill', '-9', '-f', 'claude.*channels'], capture_output=True)
    subprocess.run(['screen', '-S', 'henry-ai', '-X', 'quit'], capture_output=True)
    await asyncio.sleep(2)
    _start_henry_screen()
    await ctx.send('Henry AI restarting...')
    for _ in range(15):
        await asyncio.sleep(2)
        if _henry_ai_running():
            await ctx.send('Henry AI is ready.')
            return
    await ctx.send('Still starting — use `!status` to check.')


@bot.command(name='status')
async def cmd_status(ctx):
    if not CONTROL_MODE:
        await ctx.send('Status command only available on Mac Mini.')
        return
    import subprocess
    procs = subprocess.run(['ps', 'aux'], capture_output=True, text=True).stdout
    henry_ai = _henry_ai_running()
    henry_bot_running = 'henry_bot.py' in procs
    screen_out = subprocess.run(['screen', '-list'], capture_output=True, text=True).stdout
    henry_screen = 'henry-ai' in screen_out
    msg = '**Henry Status**\n'
    msg += f'- Henry AI (Claude): {"✅ Running" if henry_ai else "❌ NOT running — use `!start henry`"}\n'
    msg += f'- Scraper bot: {"✅ Running" if henry_bot_running else "❌ NOT running"}\n'
    msg += f'- Screen session: {"✅ Active" if henry_screen else "❌ Not found"}'
    await ctx.send(msg)


@tasks.loop(seconds=30)
async def rate_limit_monitor():
    """Watch Henry AI screen log for rate limit messages and alert Discord."""
    global _rate_limit_alerted
    if not IS_MAC_MINI or not HENRY_AI_LOG.exists():
        return
    try:
        size = HENRY_AI_LOG.stat().st_size
        with open(HENRY_AI_LOG, 'rb') as f:
            f.seek(max(0, size - 4096))
            tail = f.read().decode('utf-8', errors='ignore')
    except Exception:
        return

    hit_limit = "You've hit your limit" in tail or "rate limit" in tail.lower()

    if hit_limit and not _rate_limit_alerted:
        _rate_limit_alerted = True
        reset_info = ''
        for line in tail.splitlines():
            if 'resets' in line.lower():
                reset_info = line.strip()
                break
        if ALERT_CHANNEL_ID:
            channel = bot.get_channel(ALERT_CHANNEL_ID)
            if channel:
                msg = '⚠️ **Henry AI hit rate limit** — paused until limit resets.'
                if reset_info:
                    msg += f'\n`{reset_info}`'
                await channel.send(msg)
    elif not hit_limit:
        _rate_limit_alerted = False


@bot.event
async def on_ready():
    log.info(f"Henry bot online — logged in as {bot.user} | mac_mini={IS_MAC_MINI}")
    if not scheduled_scrape.is_running():
        scheduled_scrape.start()
        log.info("Scrape scheduler started — every 30 min, 8am–2:30am San Diego")
    if not daily_epc_scrape.is_running():
        daily_epc_scrape.start()
        log.info("EPC scheduler started — daily at 6 AM San Diego")
    if IS_MAC_MINI and not rate_limit_monitor.is_running():
        rate_limit_monitor.start()
        log.info("Rate limit monitor started")


@tasks.loop(minutes=30)
async def daily_epc_scrape():
    """Run EPC forward rate scrape once daily at 6 AM San Diego time."""
    sd_now = datetime.now(SD_TZ)
    if sd_now.hour != 6:
        return
    log.info("Daily EPC scrape starting — 6 AM San Diego")
    await asyncio.to_thread(run_epc_scrape)


@tasks.loop(minutes=30)
async def scheduled_scrape():
    """Run the rate scraper every 30 minutes during San Diego operating hours."""
    sd_now = datetime.now(SD_TZ)
    sd_hour, sd_min = sd_now.hour, sd_now.minute
    in_hours = sd_hour >= 8 or sd_hour <= 1 or (sd_hour == 2 and sd_min <= 30)

    if not in_hours:
        log.info(f"Scrape skipped — outside hours ({sd_now.strftime('%I:%M %p')} SD)")
        return

    log.info(f"Scheduled scrape starting — {sd_now.strftime('%I:%M %p')} SD")
    rates, xlsx_path = await asyncio.to_thread(live_scrape_tonight)
    if not rates:
        log.warning("Scheduled scrape returned no data — check rate_scroll.py logs")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if not BOT_TOKEN:
        print("❌ HENRY_DISCORD_BOT_TOKEN not set in .env")
        print("   1. Go to discord.com/developers/applications")
        print("   2. Create a new application → Bot → copy the token")
        print("   3. Add HENRY_DISCORD_BOT_TOKEN=your-token to .env")
        exit(1)

    log.info("Starting Henry bot...")
    bot.run(BOT_TOKEN)
