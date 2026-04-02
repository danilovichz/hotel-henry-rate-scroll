# Health Check Protocol — Henry Knowledge Base

_Full protocol for the daily 7am system health check. Load this whenever a health check is triggered._

---

## When This Runs

- **Automatically:** henry_bot.py posts a trigger to Discord every morning at 7am San Diego time
- **Manually:** Anyone says `!health`, `@Henry run health check`, or `@Henry daily brief`

---

## How to Execute

1. Run the data gatherer:
   ```bash
   python3 ~/henry/scripts/health_check.py --pretty
   ```

2. Read the JSON output — four sections: `scrape_24h`, `system_health`, `patterns_7d`, `log_scan`

3. Apply autonomous fixes where permitted (see below)

4. Post the structured Discord brief (see format below)

5. If anything needs human action — post clear, actionable instructions. Never just say "something's wrong."

---

## Interpreting Results — Thresholds

### Scrape Run Completion
| Completion % | Status |
|---|---|
| ≥ 90% of expected | ✅ OK |
| 70–89% | ⚠️ Degraded — flag in brief |
| < 70% | 🔴 Critical — escalate immediately |

_Expected runs per day: 37 (every 30 min, 8am–2:30am San Diego)_

### Hotel ERR Rate
| ERR Rate | Window | Status |
|---|---|---|
| < 10% | 24h | ✅ OK |
| 10–25% | 24h | ⚠️ Watch — note in brief |
| > 25% | 24h | 🔴 Problem — flag and diagnose |
| > 20% | 7 days | 🔴 Systematic — escalate |

### EPC Session Age
| Age | Status |
|---|---|
| < 5 days | ✅ OK |
| 5–7 days | ⚠️ Refresh recommended soon |
| > 7 days | 🔴 Likely expired — alert humans immediately |

### Suspicious SOLD OUT
Any row where `is_sold_out=True` but IHG shows a real rate → flag. This was a known bug where Firecrawl bot challenges were misread as SOLD OUT. If pattern repeats, the proxy fix may have regressed.

### Rate Position (7-day)
| Our Rate vs Comp Avg | Action |
|---|---|
| Within ±15% | ✅ No flag needed |
| More than 15% below comp avg | ⚠️ Flag for Bobby/Darshan review |
| More than 30% below comp avg | 🔴 Urgent flag — we are leaving significant revenue on the table |

---

## Autonomous Fixes (Do Without Asking)

These are known, reversible, safe to execute without confirmation:

### Screen session dead
If `system_health.screen_session_alive = false`:
```bash
cd ~/henry/logs && screen -L -dmS henry-ai ~/henry/scripts/start-henry-ai.sh
```
Verify with `screen -ls` after 10 seconds. Report in brief: "Henry AI screen session was down — restarted automatically."

### Rate limit in screenlog
If `log_scan.rate_limit_hits > 0`: No action needed. The `rate_limit_monitor` in henry_bot.py already fires a Discord alert when this happens. Just note it in the brief.

---

## Escalate to Humans (Post Diagnosis, Do NOT Fix)

For these issues: post a clear explanation + exact steps for the human to follow.

### EPC session expired
```
🔴 EPC session needs refresh — age: X days.

Darshan: please refresh via DeskIn.
1. Open DeskIn → connect to Mac Mini
2. Open Terminal
3. Run: cd ~/henry/scripts && python3 setup_epc_session.py
4. A Chrome window opens — log in with MFA (check email for code)
5. Once you reach the EPC dashboard, session saves automatically
Takes ~5 min. EPC rate data will resume on next scrape after refresh.
```

### henry_bot.py not running
```
🔴 henry_bot.py is DOWN — scraping has stopped.

Dani: restart via SSH:
launchctl kickstart gui/501/com.henry.bot

Or check logs: tail -50 ~/henry/scripts/logs/launchd_err.log
```

### Hotel ERR rate > 40% over 7 days
Post diagnosis with specifics: which hotel, what error pattern from logs, and suggest checking Firecrawl plan/credits at firecrawl.dev dashboard. Do NOT edit rate_scroll.py autonomously.

### Unusual rate anomaly
If our hotel is suddenly 30%+ below comp avg with no comp movement visible → flag immediately for Bobby/Darshan:
```
⚠️ Rate position alert: Our rate avg $X vs comp avg $Y over the past 7 days.
This is a X% gap below market. Flagging for Bobby/Darshan review.
No rate changes made — this is for awareness only.
```
**Never suggest or make a rate change. That is Bobby's decision.**

---

## Discord Brief Format

Keep it short. If everything is green, the brief is 5–6 lines. Only expand sections where something needs attention.

```
🏨 **Henry Daily Brief** — {Day, Month Date}

**📊 Scrape Health (last 24h)**
{✅/⚠️/🔴} {N}/{expected} runs completed ({pct}%)
{Only list hotels with ERR rate > 10% or suspicious SOLD OUT — skip if all clean}

**💰 Rate Position (latest scrape — {time})**
Our rate: ${expedia} Expedia | ${ihg} IHG
Comp avg: ~${comp_avg} | {✅ in range / ⚠️ X% below market}

**🔧 System Status**
{✅/🔴} henry_bot: {running / DOWN ← action required}
{✅/🔴} Henry AI: {running / DOWN ← action required}
{✅/⚠️/🔴} EPC session: {X.X days old — ok / refresh soon / REFRESH REQUIRED}

**🔍 7-Day Patterns**
{Skip this section entirely if no flags. Only include if something needs attention.}

**⚡ Actions Taken**
{List autonomous fixes performed, or "None needed — all systems nominal"}
```

### Example — All Green
```
🏨 **Henry Daily Brief** — Thursday, April 3

**📊 Scrape Health (last 24h)**
✅ 36/37 runs completed (97%)

**💰 Rate Position (latest scrape — 2:14 AM)**
Our rate: $174 Expedia | $150 IHG
Comp avg: ~$196 | ✅ within normal range

**🔧 System Status**
✅ henry_bot: running
✅ Henry AI: running
✅ EPC session: 1.8 days old — ok

**⚡ Actions Taken**
None needed — all systems nominal
```

### Example — Issues Found
```
🏨 **Henry Daily Brief** — Friday, April 4

**📊 Scrape Health (last 24h)**
⚠️ 28/37 runs completed (76%) — degraded
⚠️ HIE SeaWorld: ERR on 8/28 runs (29%) — Firecrawl proxy issue

**💰 Rate Position (latest scrape — 2:44 AM)**
Our rate: $174 Expedia | $150 IHG
Comp avg: ~$196 | ⚠️ 11% below market — within watch range

**🔧 System Status**
✅ henry_bot: running
🔴 Henry AI: screen session was down — restarted automatically
⚠️ EPC session: 5.2 days old — refresh recommended before Apr 9

**🔍 7-Day Patterns**
⚠️ Our avg $123 vs comp avg $173 (-28.9%) — flagging for Bobby/Darshan

**⚡ Actions Taken**
- Restarted Henry AI screen session (was down)
- Flagged EPC session age for Darshan
```

---

## Quick Reference — health_check.py Output Fields

| Field | Meaning |
|---|---|
| `scrape_24h.total_runs` | Distinct scrape runs today |
| `scrape_24h.hotels[X].errors` | Firecrawl/parse failures for hotel X |
| `scrape_24h.hotels[X].suspicious_sold_out` | SOLD OUT on Expedia but IHG has rate → likely bot challenge |
| `system_health.epc_session_status` | `ok` / `refresh_soon` / `likely_expired` / `missing` |
| `system_health.screen_session_alive` | Is `henry-ai` screen running |
| `patterns_7d.rate_gap_pct` | Our avg rate vs comp avg % over 7 days |
| `patterns_7d.flags` | Pre-computed flag strings worth including in brief |
| `log_scan.rate_limit_hits` | Claude rate limit occurrences in screenlog |
