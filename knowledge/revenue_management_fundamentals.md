# Revenue Management Fundamentals — Henry Knowledge Base

_Source: Yield Management YouTube training (hotel revenue management expert)_
_Extracted: 2026-03-23_

---

## Why Yield Management Matters

Hotels have **high fixed costs**. Revenue changes do NOT cause proportional cost changes:
- Revenue goes up → costs stay mostly flat → **very profitable**
- Revenue goes down → costs still don't decrease much → **very unprofitable**

This asymmetry means yield management has an **outsized impact on profitability** compared to almost any other operational lever.

Yield management lets you **see into the future** — you see revenue for future dates while there's still time to act. Without it:
- You sell rooms too cheaply at the last minute and still end up with vacancy
- You miss opportunities to raise rates when demand is building

---

## Core Data Points Required

### 1. Dates Forward (90–365 days)
- Always looking **forward from today**, not backward
- Most hotels actively manage the next **90–120 days**
- Can extend to 180 or 365 days for visibility
- Historical same-period-last-year data is useful as a benchmark

### 2. Occupancy / Availability (from PMS)
- PMS is the **single source of truth** — reflects ALL channels (OTAs, direct, phone, walk-in)
- "Occupancy" = reservations on books for each future date
- "Availability" = the flip side — rooms NOT yet reserved
- Must include every room type, every date

### 3. Your Rates (effective consumer-facing rates)
- Not rack rate in isolation — the **effective final rate the consumer sees**
- After all modifiers: packages, promotions, discounts, meals
- Pull from the same source as competitor rates for apples-to-apples comparison

### 4. Competitor Rates
- Must be the **final consumer rate** displayed publicly
- Sources: Expedia partner tools (free but property-level only), OTA Insight, RevCaster, Profit, or Booking.com scraping
- Expedia free tool: lowest available rate per property. ~90–95% accurate. The 5–10% inaccuracy happens when a comp has sold out cheap rooms, so their "lowest" rate is actually a more expensive room type

### 5. Booking Window
- **Critical concept**: how far in advance do guests typically book?
- Business/urban hotels: 2–3 weeks average (some book day-before)
- Resort/leisure: 30–60+ days average
- If rooms are unsold inside the booking window, they become **very hard to sell**
- Must manage pricing tightly in the zone where the bulk of bookings happen

---

## Key Ratios to Track

### Ratio 1: Unsold Rooms ÷ Days Left to Sell
- Low ratio (green) = healthy — plenty of time to sell remaining rooms
- High ratio (red) = danger — too many rooms left with too little time
- Example: 5 rooms unsold with 49 days left = fine. 12 rooms unsold with 5 days left = problem

### Ratio 2: Your Effective Rate vs Comp Set Average
- Below 100% = you're priced below the market (gaining volume, losing revenue per room)
- Above 100% = you're priced above the market (gaining revenue per room, may lose volume)
- Track this ratio for every future date to spot where you're out of line

### Ratio 3: Rate Elasticity (Advanced)
- When you drop your rate, you need to gain **enough extra volume** to offset the lower price
- If you lower your rate and also lose volume (from rate parity problems) = worst of both worlds

---

## Pattern Recognition: What Signals Mean

### Signal: Occupancy Unusually LOW for a Future Period
**Diagnosis:** Compare your rates to comp set
- If your rates are significantly **above** comp set average → you're losing bookings to competitors
- **Action:** Lower rates to realign with market. Target the specific dates where the gap is widest

### Signal: Occupancy Unusually HIGH for a Future Period
**Diagnosis:** Something is driving demand — event, competitor mispricing, competitor closed rooms
- If comp set rates have **risen** → market-wide demand increase
- **Action:** RAISE rates. You're underpriced. Maintain the same relative position vs comp set but at higher absolute rates
- You're currently a "better value" which is filling rooms, but you're leaving money on the table

### Signal: Competitor Goes Sold Out
**Diagnosis:** Demand exceeded their supply. Their remaining demand flows to you
- **Action:** Hold or raise rates. You have pricing power as remaining supply shrinks

### Signal: Competitor Drops Rate Hard
**Diagnosis:** They're seeing weak demand, or distress pricing to fill rooms
- **Action:** Evaluate — don't blindly follow. Check if YOUR occupancy is also weak. If your pickup is healthy, hold your rate. Only match if you're also losing volume on those dates

### Signal: Comp Set Average Drops But Your Occupancy Is Fine
**Diagnosis:** Comp is panicking but you're not affected — maybe different segments, better reputation, better location
- **Action:** Hold rate. Monitor for 2–3 check cycles. Only adjust if your own pickup starts declining

---

## How Rate Changes Should Flow (Channel Manager Architecture)

### Method 1: Adjust Rack Rate at PMS Level (RECOMMENDED)
```
PMS rack rate change
  → Channel manager applies automatic modifiers (packages, net rates, breakfast add-on)
  → Pushes modified rates to ALL channels automatically
  → Booking engine, Expedia, Booking.com, all others update
  → Discounts/promotions applied automatically at each channel
  → Rate parity maintained automatically
```
**Advantages:** Fast, automatic, maintains parity, one change flows everywhere
**This is the method Henry should recommend when suggesting rate changes**

### Method 2: Adjust Promotional Rates Per Channel (NOT RECOMMENDED)
```
Keep PMS rack rate unchanged
  → Manually adjust discount/promotion at booking engine
  → Manually adjust at Expedia
  → Manually adjust at Booking.com
  → Manually adjust at every other channel
```
**Problems:**
- Time-consuming (some properties: 2 people × 2 days)
- Easy to make mistakes
- Rate parity breaks → channels reduce your visibility → you get lower rate AND less volume
- Worst of both worlds scenario

---

## Rate Parity — Critical Rule

All channels must show the same (or very similar) rate. When parity breaks:
- OTAs **demote your listing** in search results (less visibility = less bookings)
- Traditional travel agents stop recommending you (their clients find cheaper rates elsewhere)
- You get a **lower rate AND lower volume** — the worst outcome

**Exceptions (ways to favor direct booking without breaking parity):**
- Require a special code for the lower direct rate (bypasses automated parity bots)
- Add value instead of lowering price (free breakfast, late checkout, parking)
- Package deals: "Book 4 nights, get 5th free" (changes the unit economics without a visible rate drop)

---

## The Spreadsheet Model

### Layout (what the rate scroll spreadsheet should look like)
- **Columns = dates** (left to right = today → 90+ days out, reads like a timeline)
- **Rows:**
  - Total rooms (for this room type)
  - Available / unsold rooms
  - Occupancy %
  - Unsold rooms ÷ days left to sell (ratio — conditional formatted green/yellow/red)
  - Your effective rate (consumer-facing)
  - Your effective rate vs comp set % (conditional formatted)
  - Current rack rate
  - **Proposed rate** (where changes are flagged)
  - Change in effective rate ($ difference from current)
  - New effective rate vs comp set %
  - Individual competitor rates
  - Average competitor rate

### Conditional Formatting Rules
- **Green:** Healthy — occupancy on track, rate vs comp in line, unsold/days ratio good
- **Yellow:** Watch — slightly off trend, worth monitoring
- **Red:** Action needed — occupancy too low, rate too far from comp set, too many unsold rooms for time remaining

### Room-Level vs Property-Level
- If you have 4 room types → replicate the entire block for each type
- Compare specific room types against equivalent competitor room types (don't compare ocean view to garden view)

---

## Manual vs Automated Revenue Management

### Manual (Spreadsheet)
- **Cost:** Free (just time)
- **Frequency:** Weekly or biweekly
- **Skill required:** Basic Excel
- **Time required:** 2–4 hours once you have a rhythm
- **Best for:** Smaller properties, those not doing RM at all, those who want control
- **Limitations:** Slower iteration, manual rate implementation

### Automated (RMS Software)
- **Cost:** $300–$2,000/month + $1,000–$10,000 setup
- **Frequency:** Daily (or even real-time)
- **Skill required:** System training (1–3 months to implement)
- **Best for:** Larger properties, those who want speed and daily optimization
- **How it works:** Pulls data from PMS automatically → you view/decide in the RMS → push rate changes directly back to PMS → flows to all channels automatically
- **Risk:** If trained staff leaves, you lose the capability until someone new is trained

### What Henry Replaces
Henry provides the **speed of an automated RMS** (real-time competitor monitoring, forward pricing, alerts) at the **cost of a manual spreadsheet** (essentially free). This is the moat — a $300–$2,000/month RMS equivalent delivered as an AI agent.

---

## Applying This to Henry's Decision-Making

When Henry evaluates a pricing question, it should apply this framework:

1. **Where are we in the booking window?** If today's date is inside the peak booking window, adjustments have maximum impact. If it's too close (inside 1–2 days), most of the bookable demand has already passed.

2. **What does our unsold rooms ÷ days left ratio look like?** High ratio = we need to be more aggressive on price. Low ratio = we have pricing power.

3. **How do we compare to the comp set?** If we're above the market and occupancy is weak → lower. If we're above and occupancy is strong → hold (we're differentiated). If comp goes sold out → raise.

4. **Is this a rate change or a promotion?** Always recommend the PMS rack rate change method (Method 1). Never suggest per-channel promotional adjustments — too complex, too error-prone, breaks parity.

5. **What's the revenue impact?** Hotels have high fixed costs. A $20 rate increase on 10 remaining rooms = $200/night pure profit (no incremental cost). Frame recommendations in dollar terms.

6. **Don't panic-match.** If one competitor drops hard, check if it's isolated (that comp is distressed) or market-wide (real demand weakness). Different diagnosis = different response.
