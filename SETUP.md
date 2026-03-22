# Henry Rate Scroll — Setup Guide

Automates the 13×/day manual rate check. Runs every 30 min via cron, scrapes Booking.com, writes to CSV + Google Sheets, alerts Discord when notable events occur.

**Status:** Script built and tested. All hotels scraping. Needs Google Sheets + Discord setup before handing to client.

---

## Step 1 — Install Dependencies

```bash
pip3 install requests python-dotenv gspread google-auth
```

---

## Step 2 — Validate Hotel URLs

Before going live, open each URL manually and confirm it shows the correct hotel:

| Hotel | URL to Check |
|---|---|
| HIE Mission Valley (Ours) | `https://www.booking.com/hotel/us/holiday-inn-express-suites-san-diego-mission-valley.html?checkin=TODAY&checkout=TOMORROW&group_adults=2&no_rooms=1` |
| Hampton Inn ⭐ | `https://www.booking.com/hotel/us/hampton-inn-san-diego-mission-valley.html` |
| Courtyard | `https://www.booking.com/hotel/us/courtyard-san-diego-mission-valley-circle.html` |
| DoubleTree ⚠️ | `https://www.booking.com/hotel/us/doubletree-club-san-diego.html` — **VALIDATE THIS ONE** |
| HIE SeaWorld | `https://www.booking.com/hotel/us/holiday-inn-express-san-diego4.html` |
| Legacy Resort | `https://www.booking.com/hotel/us/the-legacy-resort-amp-spa.html` |

> ⚠️ **DoubleTree returned $60 in first test — suspect slug.** Confirm with Darshan which DoubleTree is on Hotel Circle and find correct Booking.com URL. Fix the `slug` value in `rate_scroll.py` if needed.

If a URL redirects or shows a different hotel, find the correct Booking.com slug by:
1. Go to Booking.com and search for the hotel
2. Open the hotel's listing page
3. Copy the slug from the URL: `booking.com/hotel/us/SLUG-HERE.html`
4. Update the `COMP_HOTELS` list in `rate_scroll.py`

---

## Step 3 — Test the Script

```bash
# Test Hampton Inn only (fastest validation)
python3 rate_scroll.py --test

# Run all hotels, skip Discord alerts
python3 rate_scroll.py --no-alerts

# Run for a future date
python3 rate_scroll.py --date 2026-04-12 --no-alerts
```

Check `data/rate_scroll_YYYY-MM-DD.csv` to confirm data is being written.

---

## Step 4 — Google Sheets Setup

### 4a. Create the spreadsheet
1. Create a new Google Sheet
2. Rename the default tab to `Rate Scroll`
3. Add headers in Row 1:
   ```
   Timestamp | Check-in | Our Rate | Our Status | Hampton Rate | Hampton Status | Courtyard Rate | Courtyard Status | DoubleTree Rate | DoubleTree Status | HIE SeaWorld Rate | HIE SeaWorld Status | Legacy Rate | Legacy Status
   ```
4. Copy the Sheet ID from the URL: `docs.google.com/spreadsheets/d/SHEET-ID-HERE/edit`

### 4b. Create a service account
1. Go to Google Cloud Console → Create project (or use existing)
2. Enable Google Sheets API and Google Drive API
3. Create a service account → Download JSON key file
4. Save the JSON to `credentials/henry-sheets.json` (in the hotel-henry folder)

### 4c. Share the sheet
- Share the Google Sheet with the service account email (from the JSON file, look for `client_email`)
- Give it Editor access

### 4d. Add to .env
```
GOOGLE_SHEETS_CREDENTIALS=/Users/danizal/dani/aios/clients/hotel-henry/credentials/henry-sheets.json
HENRY_RATE_SCROLL_SHEET_ID=your-sheet-id-here
```

---

## Step 5 — Discord Webhook Setup

1. In Discord, right-click the `#henry` channel → Edit Channel → Integrations → Webhooks → Create Webhook
2. Copy the webhook URL
3. Add to `.env`:
   ```
   HENRY_DISCORD_WEBHOOK=https://discord.com/api/webhooks/XXXXX/YYYYY
   ```

Test it:
```bash
python3 rate_scroll.py  # Should post an alert to #henry if any conditions trigger
```

---

## Step 6 — Cron Setup (macOS)

Run every 30 minutes, 24/7:

```bash
crontab -e
```

Add this line (adjust the path):
```cron
*/30 * * * * cd /Users/danizal/dani/aios/clients/hotel-henry/scripts && /usr/bin/python3 rate_scroll.py >> logs/cron.log 2>&1
```

Verify it's running:
```bash
crontab -l
tail -f /Users/danizal/dani/aios/clients/hotel-henry/scripts/logs/cron.log
```

---

## Step 7 — Deploy to Railway (Production)

For production (so it survives power outages and Mac restarts):

1. Create a Railway account at railway.app (~$5/month)
2. Create a new project, connect this folder as a GitHub repo
3. Set all environment variables in Railway's settings panel (same as .env)
4. Add a `Procfile`:
   ```
   worker: while true; do python3 rate_scroll.py; sleep 1800; done
   ```
5. Deploy — Railway runs it continuously

---

## Alert Conditions

The script automatically posts to `#henry` when:

| Trigger | Example Alert |
|---|---|
| Comp just went sold out | 🔴 **Hampton Inn** just went SOLD OUT. We have inventory — raise rate? |
| Comp came back from sold out | 🟡 **Courtyard** back in inventory at $229. Monitor. |
| Comp dropped rate ≥ $15 | ⚠️ **Hampton Inn** dropped $20 ($187 → $167). We're at $245. Respond? |
| Comp pricing $30+ above us | 💡 **Legacy Resort** is $64 above us ($309 vs our $245). Room to raise? |

---

## Data Format

`data/rate_scroll_YYYY-MM-DD.csv` — one row per hotel per scrape run:

| run_timestamp | checkin | hotel_name | lowest_rate_usd | is_sold_out | availability_signal | rooms_left | room_type |
|---|---|---|---|---|---|---|---|
| 2026-03-22 20:34:15 | 2026-03-22 | Hampton Inn | 187 | False | available | 4 | Standard Queen Room |

---

## Next Steps (Phase 2)

Once rate scroll is validated and running:
- [ ] Add noraview Apify actor for 90-day forward pricing scan (runs 6am daily)
- [ ] Feed historical data + forward scan into Henry's context
- [ ] Build Henry's rate recommendation engine on top of this live feed
- [ ] Connect to channel manager API for real-time room count (replaces Booking.com availability proxy)
