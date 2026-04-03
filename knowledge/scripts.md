# Scripts — Hotel Henry Knowledge Base

_Every script in this repo. What it does, how to run it, expected outputs._

---

## Repository

**Repo name:** `hotel-henry-rate-scroll`
**Local path (Dani's machine):** `/Users/danizal/dani/aios/clients/hotel-henry/scripts/`
**Mac Mini path:** `~/henry/scripts/`
**Sync:** Push from local → `git push` → pull on Mac Mini → `git pull`

---

## Primary Scripts

### henry_bot.py — The Main Discord Bot

**What it does:**
- Connects to Discord as Henry Bot
- Provides `!rates`, `!rates live`, `!henry [question]` commands
- Provides management commands: `!start henry`, `!stop henry`, `!restart henry`, `!status`
- Posts rate scroll Excel file to Discord every 30 minutes (via scheduler)
- Sends proactive alerts when market conditions change

**How to run:**
```bash
python3 henry_bot.py
```

**Runs as:** launchd service (`com.henry.bot`) on Mac Mini — auto-starts on boot
**Log file:** `~/henry/scripts/logs/henry_bot.log`

**Discord commands:**
| Command | What it does |
|---------|-------------|
| `!rates` | Returns current rate scroll from last scrape |
| `!rates live` | Triggers fresh scrape, returns live results |
| `!henry [question]` | AI analysis with full market context |
| `!start henry` | Starts Henry AI in a new screen session |
| `!stop henry` | Kills Henry AI process and screen session |
| `!restart henry` | Stop + start Henry AI |
| `!status` | Shows what's running (Henry AI, scraper bot, screen session) |

---

### collect_epc_rates.py — Expedia Partner Central Rate Scraper

**What it does:**
- Logs into Expedia Partner Central backend using Henry's account
- Scrapes structured rate data for all 5 comp hotels
- Pulls events calendar with projected attendances
- Returns structured rate data without needing to scrape individual hotel pages

**How to run:**
```bash
python3 collect_epc_rates.py
```

**Credentials:** henry@gmail.com — credentials stored in `.env` file or passed via EPC session

---

### rate_scroll.py — Rate Scroll Excel Generator

**What it does:**
- Takes scraped rate data
- Generates Excel file matching Darshan's Rate Shop template exactly
- Fills rows 3–9 (rows 10–17 are manual staff entries)
- Outputs file to `data/` folder

**How to run:**
```bash
python3 rate_scroll.py
```

**Output:** Excel file in `data/` matching this format:
```
Row 3: Rooms Left to Sell (our hotel)
Row 4: Our Express HC (IHG rate + Expedia rate columns)
Row 5: HIE SeaWorld (IHG + Expedia columns)
Row 6: HIE Old Town (IHG + Expedia columns)
Row 7: HIE Downtown (IHG + Expedia columns)
Row 8: Courtyard Marriott (Expedia only, X in IHG)
Row 9: Hampton Inn (Expedia only, X in IHG)
```

---

### run_rate_scroll.sh — Shell Runner for Rate Scroll

**What it does:**
- Shell wrapper that runs the full rate scroll pipeline
- Calls collect + generate + post to Discord

**How to run:**
```bash
bash run_rate_scroll.sh
```

---

### setup_epc_session.py — EPC Session Setup

**What it does:**
- Handles login and session management for Expedia Partner Central
- Stores session cookies for subsequent API calls
- Run once to establish session before rate collection

**How to run:**
```bash
python3 setup_epc_session.py
```

---

### auto_epc_login.py — Automated EPC Login

**What it does:**
- Automates the EPC login flow
- Handles 2FA or session refreshes if needed

---

### run_epc.py — EPC Rate Pull Orchestrator

**What it does:**
- Orchestrates the full EPC rate pull pipeline
- Calls setup, login, scrape in sequence

**How to run:**
```bash
python3 run_epc.py
```

---


### health_check.py — Daily System Health Report

**What it does:**
- Reads last 24h of rate_scroll CSVs and analyzes scrape run health
- Checks henry_bot.py, Henry AI screen session, and EPC session status
- Scans logs for recent errors and rate limit hits
- Analyzes 7-day patterns for systematic hotel ERR rates and rate positioning
- Returns structured JSON report for Henry AI to interpret and act on

**How to run:**
```bash
python3 health_check.py           # JSON to stdout
python3 health_check.py --pretty  # Pretty-printed JSON
```

**Output:** Structured JSON with four sections: `scrape_24h`, `system_health`, `patterns_7d`, `log_scan`.

**When to run:** Automatically triggered at 7am via henry_bot.py daily_health_check task. Also run manually for ad-hoc system checks.

**See also:** `knowledge/health-check.md` for interpretation thresholds, autonomous fix rules, and Discord brief format.

---
### test_sources.py — Test All Data Sources

**What it does:**
- Tests that all scraping sources are reachable
- Validates that rate extraction is working
- Run this when debugging scrape failures

**How to run:**
```bash
python3 test_sources.py
```

---

### test_expedia_backend.py — Test EPC Access

**What it does:**
- Tests specifically the Expedia Partner Central backend
- Validates login, session, and data extraction

**How to run:**
```bash
python3 test_expedia_backend.py
```

---

### auto-update.sh — Auto Pull Latest Code

**What it does:**
- Pulls latest code from GitHub on Mac Mini
- Restarts relevant services if code changed

---

## Configuration Files

### .env (not in repo — create locally)
Required environment variables:
```
DISCORD_BOT_TOKEN=<henry scraper bot token>
EPC_EMAIL=henry@gmail.com
EPC_PASSWORD=<from Darshan>
OPENROUTER_API_KEY=<for !henry analysis responses>
```

### requirements.txt
Python dependencies. Install with:
```bash
pip install -r requirements.txt
```

### railway.toml + Procfile
Deployment config for Railway. Railway runs `henry_bot.py` as the main process.

---

## Infrastructure

### Mac Mini (Henry AI)

| Item | Detail |
|------|--------|
| ZeroTier IP | 192.168.193.204 |
| SSH | `ssh rentamac@192.168.193.204` (password: rentamac) |
| Screen session | `screen -r henry-ai` (attach to Henry AI session) |
| Start Henry AI | `screen -dmS henry-ai ~/henry/scripts/start-henry-ai.sh` |
| Kill Henry AI | `pkill -9 -f 'claude.*channels'` |
| Henry workspace | `~/henry/workspace/` |
| Scripts folder | `~/henry/scripts/` |

**Henry AI start script** (`~/henry/scripts/start-henry-ai.sh`):
```bash
#!/bin/zsh
source ~/.zshenv
security unlock-keychain -p rentamac ~/Library/Keychains/login.keychain-db 2>/dev/null
cd ~/henry/workspace
exec ~/.local/bin/claude --dangerously-skip-permissions --channels plugin:discord@claude-plugins-official
```

**Claude Code settings** (`~/.claude/settings.json` on Mac Mini):
```json
{
  "channelsEnabled": true,
  "enabledPlugins": {"discord@claude-plugins-official": true},
  "model": "claude-sonnet-4-6",
  "permissions": {
    "allow": ["Bash(*)", "Read(*)", "Write(*)", "Edit(*)", "MultiEdit(*)", "Glob(*)", "Grep(*)"],
    "deny": []
  }
}
```

**Discord plugin config** (`~/.claude/channels/discord/access.json` on Mac Mini):
- Dani's user ID: 1218674668484034691 (allowed in DMs and server)
- Server channel: 1485316410161893528
- requireMention: true (in server, must @Henry)

### Railway (Scraper Bot)

- Runs `henry_bot.py`
- Auto-deploys on push to main branch
- Env vars set in Railway dashboard
- Cost: ~$5/month

### Discord Setup

| Item | Detail |
|------|--------|
| Henry AI bot App ID | 1486777021500493965 |
| Henry AI Discord token | In `~/.claude/channels/discord/.env` on Mac Mini |
| Henry scraper bot token | In `.env` / Railway env vars |
| Server channel (rate scroll) | #henry (ID: 1485316410161893528) |
| Discord channel for Henry AI | Same server — message with @henry mention |

---

## Templates

**`templates/`** — Contains the Excel Rate Shop template that matches Darshan's format exactly.

Use as reference when generating the output Excel file.

---

## Data Folder

**`data/`** — Output folder for generated rate scroll Excel files.

Files are named with timestamp and posted to Discord.

---

## Logs

**`logs/`** — Log files for the bot and scraper.

```bash
tail -f ~/henry/scripts/logs/henry_bot.log  # Follow live log
```

---

## auto_health_check.py

**Purpose:** Standalone system monitor — checks scrape health, data quality, system processes, and posts to Discord via webhook. No Claude / Henry AI dependency required.

**Runs via:** launchd `com.henry.autocheck` every 30 minutes automatically.

**Modes:**
- Default (every 30 min): posts to Discord only if a critical issue is detected (silent when all is healthy)
- 7:00–7:29 AM SD window: automatically posts full daily brief
- `--daily` flag: force full daily brief regardless of time

**Usage:**
```bash
python3 ~/henry/scripts/auto_health_check.py           # Critical check (silent if OK)
python3 ~/henry/scripts/auto_health_check.py --daily   # Force full daily brief
```

**What it checks:**
- henry_bot.py running (pgrep)
- Henry AI process running (pgrep)
- EPC session age (flags if expired)
- Data quality: all-SOLD-OUT run, missing Expedia rates, missing XLSX
- 7-day patterns from health_check.py

**Posts to:** #henry channel (ID: 1485316410161893528) via HENRY_DISCORD_WEBHOOK

**Dependencies:** stdlib only (json, subprocess, urllib.request, zoneinfo) — no pip packages required

**See also:** `knowledge/health-check.md` for thresholds and protocol
