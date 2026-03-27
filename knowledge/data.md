# Data Assets — Hotel Henry Knowledge Base

_All data available for Henry to analyze. What exists, where it lives, what's missing._

---

## Historical Hotel Data (Available Now)

| File | What It Contains | Date Range | Status |
|------|-----------------|------------|--------|
| `Express Date Range.xlsx` | Daily Occ / ADR / Revenue from PMS | Aug 2023 – Feb 2025 | ✅ Have it |
| `Occupancy & ADR Summary.xlsx` | Daily Occ / ADR / Revenue from PMS | Feb 2025 – Feb 2026 | ✅ Have it |
| Monthly STAR reports (37 files) | Competitive benchmarking vs. 5-hotel comp set | Jan 2023 – Jan 2026 | ✅ Have it |
| Monthly reports (10 files) | Additional STR reports (same format) | Jan–Dec 2024 | ✅ Have it |
| `Occupancy Forecast.xlsx` | Current booking pace for all future dates | Mar–Dec 2026 (snapshot) | ✅ Have it |
| `IHG Corporate Accounts.xlsx` | 84 active direct-bill accounts | Current as of Mar 10, 2026 | ✅ Have it |

**Combined historical daily data:** ~32 months of Occ/ADR/Revenue (Aug 2023–Feb 2026)
**Competitive benchmarking:** 3 years of monthly STAR reports (Jan 2023–Jan 2026)

---

## Live Data (Operational — Phase 1)

| Source | What It Contains | How We Access |
|--------|-----------------|---------------|
| Expedia Partner Central | Rate shop (all 5 comps), events calendar, search demand, minimum stay indicators | henry@gmail.com login |
| Booking.com (public) | Competitor rates, room availability, "X left" counts | Firecrawl scraping |
| PMS Occupancy Forecast | Current booking pace for future dates | Manual export from Chris |

---

## Pending Data (Client to Provide)

| Data | Phase | Status |
|------|-------|--------|
| Historical rate shop files (2024–2025) | Phase 2 | ⏳ Darshan sending |
| PMS occupancy export with timestamps (2 years) | Phase 4 | ⏳ Request from Chris |
| Reservation log (booking made date + stay date, 2 years) | Phase 5 | ⏳ Request from Chris |
| Negotiated corporate rates and contract periods | Analysis | ❌ Not in current export |
| Booking.com slugs for HIE Old Town and HIE Downtown | Phase 1 | ⏳ Darshan to send |
| Arbitrary value for "rooms not shown" per hotel | Phase 1 | ⏳ Darshan to send |
| Henry's EPC account credentials | Phase 1 | ⏳ henry@gmail.com — Darshan creating |

---

## STR STAR Report — What's In It

Monthly competitive benchmarking reports. Each report contains:

- **Occupancy:** Our % vs. comp set average
- **ADR:** Our average daily rate vs. comp set average
- **RevPAR:** Revenue per available room vs. comp set average
- **MPI** (Market Penetration Index) = Our Occ ÷ Comp Set Occ × 100
- **ARI** (ADR Rate Index) = Our ADR ÷ Comp Set ADR × 100
- **RGI** (Revenue Generation Index) = Our RevPAR ÷ Comp Set RevPAR × 100

**STR comp set (5 hotels, 920 total rooms):**
- Courtyard San Diego Mission Valley/Hotel Circle (321 rooms)
- DoubleTree by Hilton Hotel San Diego - Hotel Circle (219 rooms)
- Hampton Inn San Diego/Mission Valley (184 rooms)
- Holiday Inn Express San Diego Sea World Area (70 rooms)
- Legacy Resort Hotel & Spa (126 rooms)

**Note:** The STR comp set includes DoubleTree and Legacy Resort. The daily rate shop does NOT. These are different comp sets for different purposes.

---

## PMS Data (Express Date Range + Occupancy Summary)

### What's Available
Daily snapshots with:
- Date
- Occupancy (% — can exceed 100% via rollaways/oversell)
- ADR (Average Daily Rate)
- Revenue

### What's Missing (Phase 4 + 5)
- **Timestamps of individual room sales** (needed to learn intraday pickup patterns)
- **Reservation-level data:** when each booking was MADE vs. what date it was FOR (booking lead time)

These are the most valuable data points for predictive pricing — they teach Henry when rooms sell and how far in advance.

---

## Expedia Partner Central Data (EPC)

Henry's EPC account: henry@gmail.com (credentials from Darshan)

| Data Type | What It Shows | Value |
|-----------|--------------|-------|
| Rate Shop | All comp rates in chart form, structured — no scraping | ⭐⭐⭐ Core |
| Events Calendar | Upcoming events with projected attendance (e.g., "Toxicology Meeting — 20,000 people") | ⭐⭐⭐ Core for event formula |
| Search Demand | YoY Expedia search volume for San Diego for any date | ⭐⭐ Strong signal |
| Competitor Rate Trends | "64 properties increased rates, 26% increase vs last year" | ⭐⭐ Market context |
| Minimum Stay Indicators | Which comps have 2-night, 3-night, 5-night minimums active | ⭐⭐ Edge case handling |
| Expanded Comp Set | 9+ hotels visible (vs 5 on Rate Shop) | ⭐ Future use |

**Why EPC is preferred over Booking.com scraping:** EPC provides structured data for all competitors in one view, plus events and search demand data that Booking.com doesn't provide.

---

## Booking.com Scraping (Fallback / Supplement)

When EPC minimum stay blended rates are misleading, scrape individual hotel pages directly.

### Booking.com URLs for Comp Set

```
Our Hotel:
https://www.booking.com/hotel/us/holiday-inn-express-suites-san-diego-mission-valley.html
?checkin=YYYY-MM-DD&checkout=YYYY-MM-DD&group_adults=2&no_rooms=1

Comp set (correct as of March 2026):
HIE SeaWorld:   https://www.booking.com/hotel/us/holiday-inn-express-san-diego4.html
HIE Old Town:   [URL pending from Darshan]
HIE Downtown:   [URL pending from Darshan]
Courtyard:      https://www.booking.com/hotel/us/courtyard-san-diego-mission-valley-circle.html
Hampton Inn:    https://www.booking.com/hotel/us/hampton-inn-san-diego-mission-valley.html
```

**Removed (were in old build, do NOT scrape):**
- DoubleTree Hotel Circle — not in active comp set
- Legacy Resort Hotel & Spa — not in active comp set

### Room Availability Logic

| What Booking.com Shows | What Henry Records |
|-----------------------|-------------------|
| "X left" (e.g., "3 left") | Use exact number |
| Nothing shown / just "available" | Use arbitrary value per hotel (Darshan to provide) |
| "Sold Out" | 0 — flag and alert |

---

## What Each Data Phase Unlocks

| Phase | Data Added | What Henry Learns |
|-------|-----------|------------------|
| 1 (Now) | Live rate scrapes every 30 min | Real-time market positioning |
| 2 | Historical rate shops 2024–2025 | Seasonal comp pricing patterns, how comps priced past events |
| 3 | Historical rate scrolls (planned rates) | Where we left money on the table |
| 4 | PMS with timestamps | Intraday pickup patterns, time-of-day demand curves |
| 5 | Reservation log (made date vs. stay date) | Booking lead times, anti-panic logic |
| 6 | Events + anomalies database | What drives unusual demand, what to ignore |

---

## Key Pricing Metrics Reference

| Term | Definition |
|------|-----------|
| ADR | Average Daily Rate — average revenue per rented room |
| Occupancy | % of rooms rented (can exceed 100% via rollaways/oversell) |
| RevPAR | Revenue Per Available Room = ADR × Occupancy |
| Pickup | Rooms booked in last 24h for a given future date |
| Pace | Cumulative rooms booked for a future date vs. historical booking curve |
| Rate Scroll | Daily spreadsheet tracking our rate + comp rates every ~2 hours |
| Floor rate | $109 (absolute minimum, never go below this) |
| Ceiling rate | No hard ceiling — observed peak ~$353, strong summer dates reach $500+ |
| MPI | Market Penetration Index = Our Occ ÷ Comp Set Occ × 100 |
| ARI | ADR Rate Index = Our ADR ÷ Comp Set ADR × 100 |
| RGI | Revenue Generation Index = Our RevPAR ÷ Comp Set RevPAR × 100 |
