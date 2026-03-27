# Strategy — Hotel Henry Knowledge Base

---

## Core Opportunity

This hotel runs at ~97% average occupancy and already outperforms its comp set by 46% on RevPAR (RGI 146 in Jan 2026).

**The opportunity is not filling rooms. It is pricing them higher on peak days.**

| Improvement | Annual Impact |
|------------|---------------|
| +$10 ADR across all days (104 rooms × 365) | +$379,600 |
| +$20 ADR on just peak 30 days (100% occ) | +$62,400 |
| Capture 5 "missed" peak pricing events/year ($500 vs $300 for 50 rooms) | +$50,000 |
| Eliminate 1 bad pricing day/month ($150 vs $200 missed on 80 rooms) | +$48,000 |

**Conservative estimate:** Henry should be worth $100K–$200K in additional annual revenue if it catches even a fraction of pricing opportunities.

---

## The Herd Hotel Rule (Bobby's Most Important Operating Principle)

> *"We are a herd of hotels that can't be front runners unless something exceptional is happening."*

At this hotel tier (select-service, Mission Valley), competitors move in blocks. When one raises rates, if 2 follow, everyone follows. When one drops, others watch and eventually follow.

**What this means for Henry:**
- **Follow the market. Do not lead it.**
- Do not recommend raising rates just because one comp is higher.
- Watch what the entire herd is doing and position within it.
- It's a race to the middle (not the bottom, not the top) — hold firm in the middle tier.
- Only deviate from the herd when something exceptional is happening (major event, comp sold out, anomalous demand spike).

**Alert logic that follows from this rule:**
- ✅ Alert when comp goes sold out → opportunity to hold or raise
- ✅ Alert when market is moving down → should we follow the herd?
- ✅ Alert when rooms unsold with high inventory late in day → risk
- ❌ DO NOT alert "comp is higher, raise rate" — wrong for a herd hotel
- ❌ DO NOT recommend raising when we have 20+ rooms unsold

---

## Bobby's 6-Step Build Roadmap (Do NOT skip steps — each builds trust)

### Step 1 — Rate Shop (Phase 1 — ACTIVE NOW)
**What:** Henry scrapes and fills the Rate Shop every 30 minutes.
**How:** Firecrawl + Expedia backend (Darshan created Henry's Expedia account)
**Output:** Excel file matching Darshan's Rate Shop template exactly, posted to Discord every 30 min

**Rate Shop format (rows Henry fills):**
```
Row 3: Rooms Left to Sell       ← Our hotel (from Expedia backend or PMS)
Row 4: Our Express HC           ← Our rate (IHG column + Expedia column)
Row 5: HIE SeaWorld             ← Lowest rate (IHG + Expedia columns)
Row 6: HIE Old Town             ← Lowest rate (IHG + Expedia columns)
Row 7: HIE Downtown             ← Lowest rate (IHG + Expedia columns)
Row 8: Courtyard Marriott       ← Lowest rate (Expedia only, X in IHG column)
Row 9: Hampton Inn              ← Lowest rate (Expedia only, X in IHG column)
```

**Rows Henry does NOT fill (manual by staff):**
- Row 10: Out of order (OOO rooms — from PMS)
- Rows 11–17: Kings Open, Arrivals, Day Use, Early Departures, Hurdle Points, Declines, Front Desk

**Bobby confirmed:**
- Rate = lowest rate across ALL room types (not a specific room type)
- Two columns per time check: IHG rate + Expedia rate
- Kings available, Queens available, Total rooms available per comp hotel
- When Booking.com shows "X left" → use exact number
- When nothing shown → use arbitrary value (Darshan to provide per hotel)
- When "Sold Out" → 0 and flag it

### Step 2 — Historical Rate Shops (Phase 2 — after trust established)
- Upload 2+ years of past rate shop files (2024–2025)
- Henry learns: trends, seasonal patterns, comp pricing history
- Bobby: *"Once we get that dialed in and we have some degree of trust, then we're going to start uploading last two years of rate shops."*
- Darshan will get Elizabeth + India team to synthesize these files

### Step 3 — Historical Rate Scrolls + Forward Pricing (Phase 3)
- Upload past 2 years of 365-day forward rate scrolls (what they PLANNED to charge)
- Upload current 2026 planned rates
- Henry compares: planned vs. actual → "where did we leave money on the table?"

### Step 4 — Occupancy + Pickup from PMS (Phase 4)
- Daily occupancy report with timestamps of each room sale
- Bobby: *"How many rooms were rented for each of the days for last two years. With timestamps."*
- Teaches Henry: intraday pickup patterns, when rooms sell, time-of-day demand curves
- Result: Henry understands pace

### Step 5 — Reservation Log (Phase 5)
- When each reservation was MADE vs. what date it was FOR
- Bobby: *"The date and time the reservation was made and what date the booking was made for."*
- Example: Booking made March 15 for July 4th → teaches lead time
- Henry learns: "80% of July 4th bookings come after June 25th — don't panic if April is empty"
- This is the anti-panic layer

### Step 6 — Events + Anomalies Database (Phase 6)
- **Recurring events:** Comic Con, July 4th, Padres season, conventions, school breaks
- **Group bookings:** Recurring corporate blocks
- **Anomalies:** One-time events (construction crew: 40 rooms for 2 months, never again)
- Bobby: *"We don't want Henry to think they're coming all the time."*
- Henry must know which is which — don't price for an anomaly that won't repeat

### End State: Predictive Analysis + Autonomous Execution
Henry says: *"Based on past 2 years + current pickup + tomorrow's events, here is what I recommend for tonight, this weekend, and July 4th."*
Eventually: Henry pushes rate changes to channel manager via API, humans approve via Discord.

---

## Event-Based Pricing Formula (Darshan's Formula)

**Baseline:** Every 10,000 event attendees = +$10 rate adjustment

**Nuances:**
- **Stack multiple events:** 3K + 10K + 20K = 33K = +$33 on that date
- **Local vs. visitor nuance:** Padres game (40K attendees) — most are San Diego locals, NOT hotel guests. Weight these lower than out-of-town events.
- **Threshold approach:** Only adjust above the daily average event attendance baseline
- Compare to baseline average attendance — only adjust above the norm
- Darshan: *"We'll let Henry figure out the analytics for this"*

---

## Two Monitoring Modes

### Mode 1: Day-Of Rate Scroll (Real-Time)
- **Dates:** Today only
- **Cadence:** Every 30 minutes, 8am–2:30am San Diego time
- **Purpose:** Intraday pricing decisions — are we leaving money on the table right now?
- **Key signals:**
  - Competitor drops rate → should we match or hold?
  - Our pickup spiking → demand is strong, raise rates
  - Competitor goes sold out → we're the last option, raise rates
  - We're at 90% occ at noon → hold rate, walk-ins coming 3–5pm

### Mode 2: Forward-Looking Scan (Strategic)
- **Dates:** Next 90 days
- **Cadence:** Once per day at 6am
- **Purpose:** Are we priced right for upcoming events, weekends, known demand dates?
- **Key signals:**
  - Future date showing comp set much higher → event just announced
  - Our rate is higher than all comps 3 weeks out → risk of getting passed over
  - Comp sold out for a future date → block booking happened, raise our rate

---

## Rate Movement Realities

- Can change up to 13× per day (every ~2 hours during monitoring)
- Rush periods: beach arrivals 3–5pm, Gaslamp/bar crowd 9–11pm walk-ins
- Strategy: hold rate as long as possible on peak days, only drop if pace falls behind
- Rate parity: channel manager syncs all channels, only need to update one place

---

## Length-of-Stay Strategy

On event weekends, single-night guests would take rooms at low rates then depart, leaving gaps that are hard to fill.

**When to apply minimums:**
- 2-night minimum: weekend events where Friday-only or Saturday-only guests would block occupancy
- 3-night minimum: major multi-day events (Comic-Con, large conventions)

Evaluate on a case-by-case basis per date.

---

## Room Type Availability Signals

- Kings sold out = especially important signal (lowest rate room gone, remaining inventory is higher-priced)
- "X left" shown on Booking.com → use exact number
- No number shown → use arbitrary value per hotel (Darshan to provide per hotel)
- "Sold Out" → 0 — flag it and alert in Discord

---

## Minimum Stay Edge Case

Some hotels set minimum night stays (e.g., 2–3 nights). When this applies:
- Expedia backend shows a blended rate (e.g., $185 for 3 nights = $61.67/night) — **this is WRONG**
- The hotel's own page shows correct nightly rate (e.g., $272/night)
- **Solution:** When a minimum stay is detected, scrape the hotel's individual page directly for the correct nightly rate.
- Expedia backend shows indicators for minimum stay requirements per competitor.

---

## Expedia Partner Central Backend (Henry's Data Source)

Darshan showed the admin center. Henry has his own account (henry@gmail.com — Darshan created).

| Data Available | What It Contains |
|---|---|
| Revenue Management → Rate Shop | All comp rates in chart form, structured data, no scraping needed |
| Events Calendar | Upcoming events with projected attendance (e.g., "Toxicology Meeting — 20,000 people") |
| Search Demand | Year-over-year Expedia search volume for San Diego |
| Competitor Rate Trends | "64 people increased rates, 26% increase vs last year" |
| Minimum Stay Indicators | Shows when comps have 2-night, 3-night, 5-night minimums |
| More Competitors | 9+ hotels visible vs 5 on the Rate Shop |

**Key insight:** EPC may be cleaner than scraping Booking.com because it has structured rate data for all competitors plus events and search demand data.

---

## Technical Stack

```
DATA PIPELINE
Primary: Expedia Partner Central backend (structured rate shop + events calendar)
Fallback: Firecrawl → Booking.com individual hotel pages

HENRY'S BRAIN
OpenRouter (google/gemini-flash) for Discord bot responses
Claude API for deep analysis (historical data, pattern recognition)

COMMUNICATION
Discord bot — Henry lives in #henry channel
  - !rates → current rate scroll from latest scrape
  - !rates live → triggers fresh scrape, returns results
  - !henry [question] → AI-powered analysis with market context
  - !start henry / !stop henry / !restart henry / !status → management commands
  - Proactive alerts: comp sold out, rate drops, rate opportunities
  - Excel file uploaded to Discord every 30 minutes

HOSTING
Railway ($5/mo) — scraper bot + Discord bot (henry_bot.py)
Cloud Mac Mini ($30/mo, Rent-a-Mac) — Henry AI (Claude Code with Discord channels)
  - ZeroTier IP: 192.168.193.204
  - SSH: ssh rentamac@192.168.193.204 (password: rentamac)
```
