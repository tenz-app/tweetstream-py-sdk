# TweetStream SDK for Python

Official Python SDK for [TweetStream](https://tweetstream.io) - the real-time Twitter WebSocket API built for crypto traders.

[![PyPI version](https://badge.fury.io/py/tweetstream-sdk.svg)](https://pypi.org/project/tweetstream-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## Why TweetStream?

- **~200ms latency** - Get tweets before they hit your feed
- **1M+ signals daily** - Battle-tested infrastructure
- **Token detection** - Automatic $ticker and contract address extraction with live prices
- **OCR built-in** - Extract text from screenshot tweets
- **CEX & prediction markets** - Detect Binance, Bybit, Polymarket mentions
- **No infrastructure** - Just connect and stream

Perfect for trading bots, Discord alerts, sentiment analysis, and real-time portfolio tracking.

## Installation

```bash
pip install tweetstream-sdk
# or with uv
uv add tweetstream-sdk
```

## Quick Start

### Real-time Tweet Streaming

```python
import asyncio
from tweetstream_sdk import TweetStreamClient, TweetContent, TweetMeta

async def main():
    client = TweetStreamClient(api_key="your-api-key")  # Get one at https://tweetstream.io

    @client.on("tweet")
    async def on_tweet(tweet: TweetContent):
        print(f"@{tweet.author.handle}: {tweet.text}")

    @client.on("tweet_meta")
    async def on_meta(meta: TweetMeta):
        if meta.detected and meta.detected.tokens:
            for token in meta.detected.tokens:
                print(f"Token: {token.symbol} | Chain: {token.chain} | Price: ${token.price_usd}")

    @client.on("connected")
    async def on_connected():
        print("Streaming tweets...")

    await client.connect()

asyncio.run(main())
```

### REST API for Historical Data

```python
from tweetstream_sdk import TweetStreamApi

api = TweetStreamApi(api_key="your-api-key")

# Fetch historical tweets for backtesting
history = api.get_history(
    handles=["elonmusk", "VitalikButerin"],
    limit=100,
    start_date="2024-01-01T00:00:00Z",
)

for tweet in history.data:
    print(f"@{tweet.twitter_handle}: {tweet.body}")

# Manage tracked accounts
api.add_accounts(["whale_alert", "lookonchain"])
api.remove_accounts("old_account")
```

## Features

### Real-time WebSocket Streaming

- **Tweet content** - Full tweet with author, media, timestamps
- **Quotes, replies, retweets** - Complete reference chain
- **Truth Social** - Stream from both Twitter/X and Truth Social
- **Profile updates** - Name, bio, avatar changes
- **Follow notifications** - Know when tracked accounts follow others
- **Auto-reconnect** - Built-in exponential backoff

### Metadata Detection

Every tweet is enriched with:

```python
@client.on("tweet_meta")
async def on_meta(meta: TweetMeta):
    if not meta.detected:
        return

    # Crypto tokens with live prices
    for token in meta.detected.tokens:
        print(f"{token.symbol} on {token.chain}: ${token.price_usd}")
        print(f"Contract: {token.contract}")

    # CEX trading pairs
    for market in meta.detected.cex:
        print(f"{market.exchange.value}: {market.symbol} @ ${market.price_usd}")

    # Prediction markets (Polymarket, Kalshi)
    for market in meta.detected.prediction:
        print(f"{market.exchange.value}: {market.title}")

    # OCR from images
    if meta.ocr:
        print(f"Image text: {meta.ocr.text}")
```

### Account Management API

```python
# Add accounts to track
result = api.add_accounts(["trader1", "trader2", "trader3"])
print(f"Added {result.summary.succeeded} of {result.summary.total}")

# Remove accounts
api.remove_accounts("old_account")

# Get historical data with filters
from tweetstream_sdk import MessageType

tweets = api.get_history(
    handles=["specific_trader"],
    message_type=MessageType.TWEET,  # or PROFILE, FOLLOW
    start_date="2024-01-01T00:00:00Z",
    end_date="2024-01-31T23:59:59Z",
    limit=500,
)
```

## Examples

### Trading Bot Alert

```python
import asyncio
from tweetstream_sdk import TweetStreamClient, TweetContent, TweetMeta

async def main():
    client = TweetStreamClient(api_key="your-api-key")
    recent_tweets: dict[str, TweetContent] = {}

    @client.on("tweet")
    async def on_tweet(tweet: TweetContent):
        recent_tweets[tweet.tweet_id] = tweet

    @client.on("tweet_meta")
    async def on_meta(meta: TweetMeta):
        if not meta.detected or not meta.detected.tokens:
            return

        tweet = recent_tweets.get(meta.tweet_id)
        for token in meta.detected.tokens:
            if token.chain == "solana":
                print(f"[ALERT] @{tweet.author.handle if tweet else 'unknown'} mentioned {token.symbol}")
                print(f"  Contract: {token.contract}")
                print(f"  Price: ${token.price_usd}")
                # Send to your trading bot...

    await client.connect()

asyncio.run(main())
```

### Discord Webhook Integration

```python
import asyncio
import aiohttp
from tweetstream_sdk import TweetStreamClient, TweetContent

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/..."

async def main():
    client = TweetStreamClient(api_key="your-api-key")

    @client.on("tweet")
    async def on_tweet(tweet: TweetContent):
        async with aiohttp.ClientSession() as session:
            await session.post(DISCORD_WEBHOOK, json={
                "content": f"**@{tweet.author.handle}**: {tweet.text}\n{tweet.link}"
            })

    await client.connect()

asyncio.run(main())
```

### Profile Change Monitor

```python
@client.on("profile_update")
async def on_profile(event: ProfileUpdateEvent):
    print(f"@{event.actor.handle} updated their profile:")
    if event.changes.name:
        print(f"  Name: {event.changes.name}")
    if event.changes.bio:
        print(f"  Bio: {event.changes.bio}")
    if event.changes.handle and event.previous:
        print(f"  Handle: @{event.previous.handle} -> @{event.changes.handle}")
```

## API Reference

### TweetStreamClient

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `api_key` | `str` | required | Your TweetStream API key |
| `base_url` | `str` | `wss://ws.tweetstream.io/ws` | WebSocket endpoint |
| `auto_reconnect` | `bool` | `True` | Auto-reconnect on disconnect |
| `max_reconnect_attempts` | `int \| None` | `None` | Max attempts (None = unlimited) |

### Events

| Event | Payload | Description |
|-------|---------|-------------|
| `tweet` | `TweetContent` | New tweet received |
| `tweet_meta` | `TweetMeta` | Token/CEX/prediction detection |
| `profile_update` | `ProfileUpdateEvent` | Profile changed |
| `follow` | `FollowEvent` | Follow event detected |
| `connected` | - | WebSocket connected |
| `disconnected` | `(code, reason)` | WebSocket disconnected |
| `reconnecting` | `(attempt, delay)` | Attempting reconnection |

### TweetStreamApi

| Method | Description |
|--------|-------------|
| `get_history(...)` | Fetch historical tweets/events |
| `add_accounts(handles)` | Add accounts to track |
| `remove_accounts(handles)` | Remove tracked accounts |

## Get Started

1. **Sign up** at [tweetstream.io](https://tweetstream.io) (7-day free trial)
2. **Get your API key** from the dashboard
3. **Install the SDK** and start streaming

```bash
pip install tweetstream-sdk
```

## Links

- [TweetStream](https://tweetstream.io) - Sign up and get your API key
- [Documentation](https://tweetstream.io/docs) - Full API docs
- [TypeScript SDK](https://github.com/tenz-app/tweetstream-ts-sdk) - TypeScript/JavaScript version

## License

MIT - See [LICENSE](LICENSE) for details.
