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
from rate_scroll import write_xlsx

SD_TZ = ZoneInfo('America/Los_Angeles')  # San Diego — handles PST/PDT automatically

import discord
from discord.ext import commands, tasks

# ─── Config ───────────────────────────────────────────────────────────────────

load_dotenv('/Users/danizal/dani/aios/.env')  # Local dev — on Railway, env vars come from dashboard

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
        [sys.executable, str(script), '--no-alerts', '--force'],
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
        except Exception as e:
            log.error(f"xlsx write failed in bot process: {e}")

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

    lines = [f"**Rate Scroll** — Check-in: `{checkin}` | Last updated: `{ts}`\n"]
    lines.append("```")
    lines.append(f"{'Hotel':<30} {'Rate':>8}  {'Status':<12}  {'Rooms':>5}")
    lines.append("─" * 60)

    for r in rates:
        name = r.get('hotel_name', '')
        flag = " ◄" if r.get('is_ours') == 'True' else ""
        if r.get('is_sold_out') == 'True':
            rate_str = "SOLD OUT"
        elif r.get('lowest_rate_usd'):
            rate_str = f"${float(r['lowest_rate_usd']):.0f}"
        else:
            rate_str = "N/A"
        status = r.get('availability_signal', '—')
        rooms = r.get('rooms_left', '—') or '—'
        lines.append(f"{name:<30} {rate_str:>8}  {status:<12}  {rooms:>5}{flag}")

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
        rate_lines.append(f"- {r['hotel_name']}{ours}: {rate_str} [{r.get('availability_signal', '?')}]{rooms}")

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
- 156 rooms, IHG franchise, Mission Valley / Hotel Circle area
- Floor rate: $109 (never price below this)
- Currently ~97% average occupancy — the opportunity is ADR optimization, not filling rooms
- Competitive set: Hampton Inn (primary comp), Courtyard, DoubleTree Hotel Circle, HIE SeaWorld, Legacy Resort
- Rate parity required across all OTAs — one rate change propagates everywhere via channel manager
- Key demand drivers: Padres games, Comic-Con, SDCC, conventions at SDCC, military events, university graduations
- Rate changes should always go through PMS rack rate (Method 1) — never per-channel promotional adjustments

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
- When suggesting rate changes, recommend adjusting the PMS rack rate — it flows automatically to all channels.
- Don't panic-match competitors. Diagnose first: is the signal isolated (one comp distressed) or market-wide (real demand weakness)?
- Consider booking window: for tonight's rates, most bookable demand has already happened. For dates 2–4 weeks out, rate changes have maximum impact.

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


@bot.event
async def on_ready():
    log.info(f"Henry bot online — logged in as {bot.user}")


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
`!rates 2026-04-12` — Rates for a specific date
`!henry [question]` — Ask Henry anything

**Example questions:**
• `!henry should I raise my rate tonight?`
• `!henry Hampton just dropped to $149, what do I do?`
• `!henry what does the comp set look like this weekend?`
• `!henry DoubleTree is sold out, what should my rate be?`"""
    await ctx.send(help_text)


# ─── Built-in Scheduler ───────────────────────────────────────────────────────

@bot.event
async def on_ready():
    log.info(f"Henry bot online — logged in as {bot.user}")
    if not scheduled_scrape.is_running():
        scheduled_scrape.start()
        log.info("Scrape scheduler started — every 30 min, 8am–2:30am San Diego")


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
