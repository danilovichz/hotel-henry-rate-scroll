#!/usr/bin/env python3
"""
EPC daily runner — called by launchd at 6:00 AM San Diego time.
Pulls EPC forward rates, writes to today's Excel, sends to Discord.
"""
import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv('/Users/danizal/dani/aios/.env')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

from collect_epc_rates import scrape_epc
from rate_scroll import write_epc_sheet, send_discord_xlsx

SD_TZ = ZoneInfo('America/Los_Angeles')


def main():
    now = datetime.now(SD_TZ)
    log.info(f"EPC daily run starting — {now.strftime('%Y-%m-%d %I:%M %p')} SD")

    try:
        epc_data = asyncio.run(scrape_epc())
        n_dates = len(epc_data.get('our_hotel', {}))
        n_comps = len(epc_data.get('competitors', {}))
        log.info(f"EPC scraped: {n_dates} dates, {n_comps} competitors")

        write_epc_sheet(epc_data)
        send_discord_xlsx(now, now.date())

        log.info("Done — EPC sheet written and sent to Discord")

    except FileNotFoundError:
        log.error("EPC session not found — run setup_epc_session.py first")
        sys.exit(1)
    except RuntimeError as e:
        if "Session expired" in str(e):
            log.error("EPC session expired — run setup_epc_session.py to refresh")
        else:
            log.error(f"EPC error: {e}")
        sys.exit(1)
    except Exception as e:
        log.error(f"EPC run failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
