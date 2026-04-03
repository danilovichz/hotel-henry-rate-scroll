#!/usr/bin/env python3
"""
Minimal Discord poster — sends a message to a channel and exits.
Called as subprocess by auto_health_check.py.
Usage: python3 discord_post.py "message text"
"""
import sys
import os
import asyncio


import os
os.environ.setdefault(
    'SSL_CERT_FILE',
    '/Users/rentamac/.homebrew/lib/python3.11/site-packages/certifi/cacert.pem'
)

def load_token():
    env_path = '/Users/rentamac/dani/aios/.env'
    try:
        for line in open(env_path).readlines():
            if line.startswith('HENRY_DISCORD_BOT_TOKEN='):
                return line.split('=', 1)[1].strip()
    except Exception:
        pass
    return os.getenv('HENRY_DISCORD_BOT_TOKEN', '')

CHANNEL_ID = 1485316410161893528

async def send_message(token: str, message: str):
    import discord
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        try:
            channel = client.get_channel(CHANNEL_ID)
            if channel is None:
                channel = await client.fetch_channel(CHANNEL_ID)
            await channel.send(message)
        finally:
            await client.close()

    await client.start(token)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: discord_post.py 'message'", file=sys.stderr)
        sys.exit(1)
    message = sys.argv[1]
    token = load_token()
    if not token:
        print("ERROR: HENRY_DISCORD_BOT_TOKEN not found", file=sys.stderr)
        sys.exit(1)
    asyncio.run(send_message(token, message))
