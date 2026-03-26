# Henry — Mac Mini Deployment Guide

This guide sets up Henry (rate scraper + Discord bot) on a new Mac Mini.
After completing it, Henry runs autonomously: scraping every 30 min, EPC forward rates at 6am, Discord bot always on.

---

## What You're Setting Up

| Component | What it does | How it runs |
|---|---|---|
| `henry_bot.py` | Discord bot + built-in 30-min scrape scheduler + 6am EPC scheduler | launchd (always on, auto-restarts) |
| `setup_epc_session.py` | One-time manual login to Expedia Partner Central | Run once manually |

> **Note:** `henry_bot.py` contains the scrape scheduler internally — you do NOT need a separate cron for `rate_scroll.py`. One process does everything.

---

## Prerequisites

On the Mac Mini, confirm these are installed:

```bash
python3 --version      # Need 3.11+
pip3 --version
```

If Python is missing, install via Homebrew:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python
```

---

## Step 1 — Get the Code on the Mac Mini

Choose **one** of the two options below. Option A (GitHub) is recommended — it means future updates are a single `git pull`.

---

### Option A — GitHub (Recommended)

The repo already exists at: `https://github.com/danilovichz/hotel-henry-rate-scroll`

**On the Mac Mini:**

```bash
ssh macmini-user@MACMINI-IP
git clone https://github.com/danilovichz/hotel-henry-rate-scroll.git ~/henry/scripts
```

**To update Henry with new code in the future:**
```bash
ssh macmini-user@MACMINI-IP
cd ~/henry/scripts
git pull
# Then restart the bot (see Day-to-Day Operations below)
```

---

### Option B — rsync (No GitHub)

From your development machine, rsync the scripts folder directly:

```bash
rsync -avz \
  --exclude '__pycache__' \
  --exclude 'data/' \
  --exclude 'logs/' \
  --exclude '.env' \
  --exclude 'data/epc_session.json' \
  /Users/danizal/dani/aios/clients/hotel-henry/scripts/ \
  macmini-user@MACMINI-IP:~/henry/scripts/
```

> Downside: every future code update requires re-running rsync manually.

---

> The EPC session (`data/epc_session.json`) is machine-specific and must be created fresh (Step 5).
> Never commit or rsync it — it contains authentication cookies.

---

## Step 2 — Create Directory Structure

SSH into the Mac Mini and create the folders Henry needs:

```bash
ssh macmini-user@MACMINI-IP
cd ~/henry/scripts
mkdir -p data logs data/epc_debug data/firecrawl_screenshots data/test_screenshots
```

---

## Step 3 — Install Dependencies

```bash
cd ~/henry/scripts
pip3 install -r requirements.txt
playwright install chromium
```

Verify:
```bash
python3 -c "import discord, playwright, requests, openpyxl; print('All good')"
```

---

## Step 4 — Set Up Environment Variables

### ⚠️ Path Fix Required

The scripts currently load `.env` from a hardcoded path (`/Users/danizal/dani/aios/.env`).
On the Mac Mini, **mirror that path** so no code changes are needed:

```bash
mkdir -p ~/dani/aios
touch ~/dani/aios/.env
```

Then open it and add all required variables:

```bash
nano ~/dani/aios/.env
```

Paste and fill in the values:

```env
# Firecrawl — rate scraper (Booking.com / Expedia)
FIRECRAWL_API_KEY=fc-xxxxxxxxxxxxxxxx

# Discord — bot token (from discord.com/developers/applications)
HENRY_DISCORD_BOT_TOKEN=xxxxxxxxxxxxxxxx

# Discord — webhook for alerts in #henry channel
HENRY_DISCORD_WEBHOOK=https://discord.com/api/webhooks/XXXXX/YYYYY

# OpenRouter — AI responses via Gemini Flash
HENRY_OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxxxxxx

# Google Sheets (optional — only if Sheets integration is active)
# GOOGLE_SHEETS_CREDENTIALS=/Users/macmini-user/henry/scripts/credentials/henry-sheets.json
# HENRY_RATE_SCROLL_SHEET_ID=your-sheet-id-here
```

> All values come from the existing Railway environment. Go to Railway → your Henry project → Variables and copy each one.

Save and test:
```bash
python3 -c "from dotenv import load_dotenv; import os; load_dotenv('/Users/macmini-user/dani/aios/.env'); print(os.getenv('FIRECRAWL_API_KEY', 'MISSING'))"
```
Should print your key, not `MISSING`.

---

## Step 5 — EPC Session Setup (Manual — Do This Once)

The Expedia Partner Central scraper needs a saved login session. This requires a display (not headless).

On the Mac Mini (with a screen connected or via Screen Sharing):

```bash
cd ~/henry/scripts
python3 setup_epc_session.py
```

A Chrome window will open. Log in to Expedia Partner Central (including MFA).
Once you reach the EPC dashboard, the session saves automatically to `data/epc_session.json`.

Verify it worked:
```bash
python3 collect_epc_rates.py --debug
```

Should print a JSON block with `our_hotel`, `competitors`, and `events` sections.

> **Session expiry:** EPC cookies expire every few weeks. When you see `Session expired` in logs, SSH in and re-run `setup_epc_session.py`.

---

## Step 6 — Test the Scraper

Before setting up the always-on process, confirm scraping works:

```bash
cd ~/henry/scripts

# Test Hampton Inn only (fastest)
python3 rate_scroll.py --test

# Test all hotels
python3 rate_scroll.py --no-alerts

# Check output
ls data/
cat data/rate_scroll_$(date +%Y-%m-%d).csv | head -5
```

You should see a CSV with 6 rows (our hotel + 5 comps).

---

## Step 7 — Set Up launchd (Always-On Bot)

launchd keeps `henry_bot.py` running 24/7 and auto-restarts it if it crashes.

### Create the plist

```bash
nano ~/Library/LaunchAgents/com.henry.bot.plist
```

Paste this (replace `macmini-user` with the actual username):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.henry.bot</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/macmini-user/henry/scripts/henry_bot.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/macmini-user/henry/scripts</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/Users/macmini-user/henry/scripts/logs/launchd.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/macmini-user/henry/scripts/logs/launchd_err.log</string>

    <key>ThrottleInterval</key>
    <integer>30</integer>
</dict>
</plist>
```

### Load it

```bash
launchctl load ~/Library/LaunchAgents/com.henry.bot.plist
```

### Verify it started

```bash
# Check it's listed as running
launchctl list | grep henry

# Watch the log
tail -f ~/henry/scripts/logs/launchd.log
```

You should see `Henry bot online — logged in as Henry#XXXX` within 10–15 seconds.

---

## Step 8 — Validate Everything End-to-End

```bash
# 1. Bot is running
launchctl list | grep henry     # Should show a PID (not a dash)

# 2. Scraper ran
ls ~/henry/scripts/data/rate_scroll_$(date +%Y-%m-%d).csv

# 3. No errors
tail -20 ~/henry/scripts/logs/launchd_err.log

# 4. Discord
# Go to #henry channel in Discord and type: !rates
# Should return a rate table within 60 seconds
```

---

## Day-to-Day Operations

### Check if Henry is running
```bash
launchctl list | grep henry
# If PID shows as "-" (not a number), it crashed — check logs
```

### View live logs
```bash
tail -f ~/henry/scripts/logs/launchd.log
```

### Restart Henry
```bash
launchctl unload ~/Library/LaunchAgents/com.henry.bot.plist
launchctl load ~/Library/LaunchAgents/com.henry.bot.plist
```

### Stop Henry
```bash
launchctl unload ~/Library/LaunchAgents/com.henry.bot.plist
```

### Refresh EPC session (when expired)
```bash
# Must have display access (Screen Sharing or physically connected)
cd ~/henry/scripts
python3 setup_epc_session.py
```

---

## Switching Off Railway

Once the Mac Mini is validated and running stable for 24–48 hours:

1. Go to Railway → Henry project → Settings → Delete service (or just pause it)
2. Update any documentation to reflect Mac Mini as the host

> Don't delete Railway until you've confirmed the Mac Mini has run at least 2 full days without issues — check that `data/` has CSV files accumulating daily.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Bot never comes online | Bad `HENRY_DISCORD_BOT_TOKEN` | Check `.env`, re-copy from Railway |
| `!rates` returns no data | Firecrawl key missing or expired | Check `FIRECRAWL_API_KEY` in `.env` |
| EPC tab empty in Excel | EPC session expired | Run `setup_epc_session.py` |
| `launchctl list` shows `-` for PID | Bot crashed on startup | `tail logs/launchd_err.log` for the error |
| Rates look wrong for DoubleTree | Booking.com slug may be wrong | Validate the URL manually per SETUP.md Step 2 |
| `.env` values not loading | Path mismatch | Confirm `~/dani/aios/.env` exists with correct username |
