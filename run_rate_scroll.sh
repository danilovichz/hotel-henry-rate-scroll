#!/bin/bash
# Henry Rate Scroll — Cron wrapper
# Runs every 30 min but only executes during San Diego operating hours
# Operating hours: 8:00 AM – 2:30 AM next day (San Diego time, handles DST automatically)

HOUR=$(TZ='America/Los_Angeles' date +%-H)
MIN=$(TZ='America/Los_Angeles' date +%-M)

# 8:00 AM to 11:59 PM (hours 8–23) → run
# 12:00 AM to 2:30 AM (hours 0–2)  → run
# 2:31 AM to 7:59 AM (hours 2–7)   → skip
if [ "$HOUR" -ge 8 ] || [ "$HOUR" -le 1 ] || ([ "$HOUR" -eq 2 ] && [ "$MIN" -le 30 ]); then
    cd /Users/danizal/dani/aios/clients/hotel-henry/scripts
    /usr/bin/python3 rate_scroll.py >> logs/cron.log 2>&1
fi
