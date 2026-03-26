#!/usr/bin/env python3
"""
Test all three data sources via Firecrawl:
1. Expedia Partner Central backend (login → Revenue Mgmt rate shop)
2. Public Expedia.com hotel pages (rates + room type breakdown)
3. IHG.com hotel pages (IHG column rates)

Run: python3 test_sources.py
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv('/Users/danizal/dani/aios/.env')
API_KEY = os.getenv('FIRECRAWL_API_KEY')
ENDPOINT = 'https://api.firecrawl.dev/v1/scrape'
HEADERS = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json',
}

SCREENSHOTS = Path(__file__).parent / 'data' / 'test_screenshots'
SCREENSHOTS.mkdir(parents=True, exist_ok=True)

# Expedia Partner Central credentials
EPC_USER = 'hotelhenryhig@gmail.com'
EPC_PASS = 'HenryClaw92108!'

# Check-in = tomorrow
CHECKIN = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
CHECKOUT = (date.today() + timedelta(days=2)).strftime('%Y-%m-%d')

def scrape(payload, label):
    print(f'\n{"="*60}')
    print(f'TEST: {label}')
    print(f'URL: {payload.get("url")}')
    try:
        r = requests.post(ENDPOINT, headers=HEADERS, json=payload, timeout=120)
        print(f'HTTP {r.status_code}')
        data = r.json()

        # Save screenshot if present
        import base64
        for path in [
            lambda d: d.get('data', {}).get('screenshot'),
            lambda d: d.get('screenshot'),
        ]:
            try:
                shot = path(data)
                if shot:
                    if shot.startswith('data:'):
                        shot = shot.split(',', 1)[1]
                    fname = SCREENSHOTS / f'{label.replace(" ", "_").replace("/", "_")}.png'
                    with open(fname, 'wb') as f:
                        f.write(base64.b64decode(shot))
                    print(f'Screenshot: {fname}')
                    break
            except Exception:
                pass

        # Print key fields
        if data.get('success'):
            d = data.get('data', {})
            extract = d.get('extract')
            md = d.get('markdown', '')
            print(f'Success: True | markdown len: {len(md)} chars')
            if extract:
                print(f'Extracted:\n{json.dumps(extract, indent=2)}')
            elif md:
                # Print first 2000 chars of markdown
                print(f'Markdown preview:\n{md[:2000]}')
        else:
            print(f'Success: False | error: {data.get("error", data)}')

        return data
    except Exception as e:
        print(f'ERROR: {e}')
        return None


# ─── TEST 1: Expedia Partner Central login ────────────────────────────────────

def test_expedia_backend():
    """Login to Expedia Partner Central via Firecrawl actions → scrape rate shop."""
    print('\n\n' + '='*60)
    print('SOURCE 1: EXPEDIA PARTNER CENTRAL BACKEND')
    print('='*60)

    payload = {
        'url': 'https://apps.expediapartnercentral.com/',
        'formats': ['screenshot', 'markdown'],
        'actions': [
            {'type': 'wait', 'milliseconds': 4000},
            {'type': 'screenshot'},
            # Google OAuth — fill email
            {'type': 'click', 'selector': '#identifierId, input[type="email"], input[name="identifier"]'},
            {'type': 'write', 'text': EPC_USER},
            {'type': 'wait', 'milliseconds': 1000},
            {'type': 'click', 'selector': '#identifierNext, [id*="Next"], button[type="submit"]'},
            {'type': 'wait', 'milliseconds': 3000},
            {'type': 'screenshot'},
            # Fill password
            {'type': 'click', 'selector': 'input[type="password"], [name="Passwd"], [name="password"]'},
            {'type': 'write', 'text': EPC_PASS},
            {'type': 'wait', 'milliseconds': 1000},
            {'type': 'click', 'selector': '#passwordNext, [id*="Next"], button[type="submit"]'},
            {'type': 'wait', 'milliseconds': 8000},
            {'type': 'screenshot'},
            # Navigate to Revenue Management
            {'type': 'click', 'selector': '[href*="revenue"], [href*="Revenue"], a[class*="revenue"], [data-testid*="revenue"], [aria-label*="Revenue"]'},
            {'type': 'wait', 'milliseconds': 5000},
            {'type': 'screenshot'},
        ],
    }
    return scrape(payload, '1_expedia_backend')


# ─── TEST 2: Public Expedia.com hotel page ────────────────────────────────────

def test_expedia_public_hampton():
    """Scrape Hampton Inn on public Expedia.com — get rate + room type breakdown."""
    print('\n\n' + '='*60)
    print('SOURCE 2: PUBLIC EXPEDIA.COM — Hampton Inn Mission Valley')
    print('='*60)

    # Hampton Inn San Diego Mission Valley — need to find this ID
    # Using a search URL first to find the hotel
    url = f'https://www.expedia.com/San-Diego-Hotels-Hampton-Inn-San-Diego-Mission-Valley.h2466.Hotel-Information?chkin={CHECKIN}&chkout={CHECKOUT}&adults=2'

    payload = {
        'url': url,
        'formats': ['extract', 'markdown', 'screenshot'],
        'actions': [
            {'type': 'wait', 'milliseconds': 4000},
            {'type': 'screenshot'},
            # Scroll down to see room types
            {'type': 'scroll', 'direction': 'down', 'amount': 800},
            {'type': 'wait', 'milliseconds': 2000},
            {'type': 'screenshot'},
            {'type': 'scroll', 'direction': 'down', 'amount': 800},
            {'type': 'wait', 'milliseconds': 2000},
            {'type': 'screenshot'},
        ],
        'extract': {
            'schema': {
                'type': 'object',
                'properties': {
                    'hotel_name': {'type': 'string'},
                    'lowest_rate_usd': {'type': 'number', 'description': 'Lowest nightly rate in USD'},
                    'is_sold_out': {'type': 'boolean'},
                    'room_types': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'name': {'type': 'string', 'description': 'Room type name e.g. Standard King, Two Queen Beds'},
                                'rate_usd': {'type': 'number'},
                                'rooms_left': {'type': 'number', 'description': 'Number shown as X left. Null if not shown.'},
                                'is_sold_out': {'type': 'boolean'},
                                'bed_type': {'type': 'string', 'enum': ['king', 'queen', 'double', 'other']},
                            }
                        },
                        'description': 'All visible room types with rates and availability counts'
                    },
                    'kings_count': {'type': 'number', 'description': 'Total king rooms shown as available (with "X left" count)'},
                    'queens_count': {'type': 'number', 'description': 'Total queen/double rooms shown as available'},
                }
            },
            'prompt': (
                f'This is an Expedia.com hotel listing page for check-in {CHECKIN}. '
                'Extract: (1) the lowest nightly rate shown in USD, '
                '(2) all room types visible — for each room type note its name, rate, bed type (king/queen/double), '
                'and how many rooms are left if shown (e.g. "3 left" = 3). '
                'If it says Sold Out, rooms_left = 0. '
                'If no count shown (just available), rooms_left = null. '
                'Count separately: how many kings are available (shown with a number), how many queens.'
            )
        }
    }
    return scrape(payload, '2_expedia_public_hampton')


def test_expedia_public_hie_oldtown():
    """Scrape HIE Old Town on public Expedia.com — known ID h5735."""
    print('\n\n' + '='*60)
    print('SOURCE 2b: PUBLIC EXPEDIA.COM — HIE Old Town (h5735)')
    print('='*60)

    url = f'https://www.expedia.com/San-Diego-Hotels-Holiday-Inn-Express-San-Diego-Airport-Old-Town.h5735.Hotel-Information?chkin={CHECKIN}&chkout={CHECKOUT}&adults=2'

    payload = {
        'url': url,
        'formats': ['extract', 'markdown'],
        'actions': [
            {'type': 'wait', 'milliseconds': 4000},
            {'type': 'scroll', 'direction': 'down', 'amount': 800},
            {'type': 'wait', 'milliseconds': 2000},
            {'type': 'scroll', 'direction': 'down', 'amount': 800},
            {'type': 'wait', 'milliseconds': 2000},
        ],
        'extract': {
            'schema': {
                'type': 'object',
                'properties': {
                    'hotel_name': {'type': 'string'},
                    'lowest_rate_usd': {'type': 'number'},
                    'is_sold_out': {'type': 'boolean'},
                    'room_types': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'name': {'type': 'string'},
                                'rate_usd': {'type': 'number'},
                                'rooms_left': {'type': 'number'},
                                'is_sold_out': {'type': 'boolean'},
                                'bed_type': {'type': 'string'},
                            }
                        }
                    },
                }
            },
            'prompt': (
                f'Expedia.com hotel listing for check-in {CHECKIN}. '
                'Extract the lowest nightly rate and all visible room types with rates, '
                'bed type (king/queen), and availability count ("X left" → use that number, sold out → 0, not shown → null).'
            )
        }
    }
    return scrape(payload, '2b_expedia_hie_oldtown')


# ─── TEST 3: IHG.com ──────────────────────────────────────────────────────────

def test_ihg_our_hotel():
    """Scrape IHG.com for our hotel rate (Holiday Inn Express San Diego Mission Valley)."""
    print('\n\n' + '='*60)
    print('SOURCE 3: IHG.COM — Our Hotel (HIE Mission Valley)')
    print('='*60)

    # IHG search for HIE Mission Valley
    checkin_parts = CHECKIN.split('-')
    checkout_parts = CHECKOUT.split('-')
    # IHG URL: search by city then select hotel
    url = f'https://www.ihg.com/holidayinnexpress/hotels/us/en/san-diego/sancv/hoteldetail?qAdlt=1&qChld=0&qCiD={checkin_parts[2]}&qCiMy={checkin_parts[1]}0{checkin_parts[0]}&qCoD={checkout_parts[2]}&qCoMy={checkout_parts[1]}0{checkout_parts[0]}&qRms=1&qRtP=6CBARC&qSlH=SANCV&qSrt=sBR&qWch=0&icdv=99801505'

    payload = {
        'url': url,
        'formats': ['extract', 'markdown', 'screenshot'],
        'actions': [
            {'type': 'wait', 'milliseconds': 5000},
            {'type': 'screenshot'},
            {'type': 'scroll', 'direction': 'down', 'amount': 800},
            {'type': 'wait', 'milliseconds': 2000},
            {'type': 'screenshot'},
        ],
        'extract': {
            'schema': {
                'type': 'object',
                'properties': {
                    'hotel_name': {'type': 'string'},
                    'lowest_rate_usd': {'type': 'number', 'description': 'Lowest IHG nightly rate in USD'},
                    'is_sold_out': {'type': 'boolean'},
                    'room_types': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'name': {'type': 'string'},
                                'rate_usd': {'type': 'number'},
                                'is_sold_out': {'type': 'boolean'},
                            }
                        }
                    }
                }
            },
            'prompt': (
                f'This is an IHG.com hotel page for check-in {CHECKIN}. '
                'Extract the lowest nightly rate in USD and all visible room types with rates. '
                'If no rooms are available, set is_sold_out=true.'
            )
        }
    }
    return scrape(payload, '3_ihg_our_hotel')


def test_ihg_hie_oldtown():
    """Scrape IHG.com for HIE Old Town rate."""
    print('\n\n' + '='*60)
    print('SOURCE 3b: IHG.COM — HIE Old Town')
    print('='*60)

    checkin_parts = CHECKIN.split('-')
    checkout_parts = CHECKOUT.split('-')
    # HIE San Diego Airport - Old Town: hotel code is likely SANOT or similar
    # Try generic IHG search for this hotel
    url = f'https://www.ihg.com/holidayinnexpress/hotels/us/en/san-diego/sanoa/hoteldetail?qAdlt=1&qChld=0&qCiD={checkin_parts[2]}&qCiMy={checkin_parts[1]}0{checkin_parts[0]}&qCoD={checkout_parts[2]}&qCoMy={checkout_parts[1]}0{checkout_parts[0]}&qRms=1&qRtP=6CBARC&qSlH=SANOA&qSrt=sBR&qWch=0'

    payload = {
        'url': url,
        'formats': ['extract', 'markdown', 'screenshot'],
        'actions': [
            {'type': 'wait', 'milliseconds': 5000},
            {'type': 'screenshot'},
        ],
        'extract': {
            'schema': {
                'type': 'object',
                'properties': {
                    'hotel_name': {'type': 'string'},
                    'lowest_rate_usd': {'type': 'number'},
                    'is_sold_out': {'type': 'boolean'},
                }
            },
            'prompt': f'IHG.com hotel detail page for check-in {CHECKIN}. Extract lowest nightly rate and hotel name.'
        }
    }
    return scrape(payload, '3b_ihg_hie_oldtown')


def test_ihg_search():
    """Search IHG.com for hotels near San Diego Mission Valley to find hotel codes."""
    print('\n\n' + '='*60)
    print('SOURCE 3c: IHG.COM SEARCH — San Diego hotels')
    print('='*60)

    checkin_parts = CHECKIN.split('-')
    checkout_parts = CHECKOUT.split('-')
    url = (
        f'https://www.ihg.com/hotels/us/en/find-hotels/hotel/results'
        f'?qDest=San+Diego%2C+CA&qCiD={checkin_parts[2]}&qCiMy={checkin_parts[1]}0{checkin_parts[0]}'
        f'&qCoD={checkout_parts[2]}&qCoMy={checkout_parts[1]}0{checkout_parts[0]}'
        f'&qAdlt=1&qChld=0&qRms=1&qRtP=6CBARC&qSrt=sBR&qBrs=6c.hi.ex.rs.ic.cp.in.sb.cw.cv.ul.vn.ki.ma.sp.nd.ct.sx.we.lx.rn.sn&icdv=99801505'
        f'&qBrand=HX'  # HX = Holiday Inn Express
    )

    payload = {
        'url': url,
        'formats': ['extract', 'markdown'],
        'actions': [
            {'type': 'wait', 'milliseconds': 5000},
            {'type': 'screenshot'},
        ],
        'extract': {
            'schema': {
                'type': 'object',
                'properties': {
                    'hotels': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'name': {'type': 'string'},
                                'hotel_code': {'type': 'string', 'description': 'IHG hotel code (e.g. SANCV, SANOA)'},
                                'rate_usd': {'type': 'number'},
                                'address': {'type': 'string'},
                            }
                        }
                    }
                }
            },
            'prompt': 'This is an IHG hotel search results page. List all Holiday Inn Express hotels shown with their names, IHG hotel codes, nightly rates, and addresses.'
        }
    }
    return scrape(payload, '3c_ihg_search')


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if not API_KEY:
        print('ERROR: FIRECRAWL_API_KEY not set')
        sys.exit(1)

    print(f'Firecrawl API Key: {API_KEY[:10]}...')
    print(f'Check-in date: {CHECKIN}')

    import sys
    test = sys.argv[1] if len(sys.argv) > 1 else 'all'

    if test in ('all', 'backend', '1'):
        test_expedia_backend()

    if test in ('all', 'expedia', '2'):
        test_expedia_public_hampton()
        time.sleep(2)
        test_expedia_public_hie_oldtown()

    if test in ('all', 'ihg', '3'):
        test_ihg_search()
        time.sleep(2)
        test_ihg_our_hotel()
        time.sleep(2)
        test_ihg_hie_oldtown()

    print(f'\n\nDone. Screenshots in: {SCREENSHOTS}')
