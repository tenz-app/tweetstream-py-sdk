# TweetStream SDK for Python

Official Python SDK for [TweetStream](https://tweetstream.io) - Real-time Twitter/X and Truth Social streaming API.

[![PyPI version](https://badge.fury.io/py/tweetstream-sdk.svg)](https://pypi.org/project/tweetstream-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## Features

- **Real-time streaming** via WebSocket with automatic reconnection
- **Full type hints** with dataclasses
- **Tweet content** including quotes, replies, and retweets
- **Metadata detection** for tokens, CEX markets, and prediction markets
- **Profile updates** and follow notifications
- **Historical data** via REST API
- **Account management** - add/remove tracked handles
- **Async-native** design with asyncio

## Installation

```bash
pip install tweetstream-sdk
```

## Quick Start

### Real-time Streaming

```python
import asyncio
from tweetstream_sdk import TweetStreamClient, TweetContent, TweetMeta

async def main():
    client = TweetStreamClient(api_key="your-api-key")

    @client.on("tweet")
    async def on_tweet(tweet: TweetContent):
        print(f"@{tweet.author.handle}: {tweet.text}")

        # Check for quoted tweets
        if tweet.ref and tweet.ref.type.value == "quote":
            print(f"  Quoting: {tweet.ref.text}")

    @client.on("tweet_meta")
    async def on_meta(meta: TweetMeta):
        if meta.detected and meta.detected.tokens:
            for token in meta.detected.tokens:
                print(f"Token detected: {token.symbol} on {token.chain}")

    @client.on("profile_update")
    async def on_profile(event):
        print(f"@{event.actor.handle} updated their profile")

    @client.on("follow")
    async def on_follow(event):
        print(f"@{event.actor.handle} followed @{event.target.handle}")

    @client.on("connected")
    async def on_connected():
        print("Connected!")

    @client.on("reconnecting")
    async def on_reconnecting(attempt: int, delay: float):
        print(f"Reconnecting in {delay:.1f}s...")

    await client.connect()

asyncio.run(main())
```

### REST API

```python
from tweetstream_sdk import TweetStreamApi, MessageType

api = TweetStreamApi(api_key="your-api-key")

# Get historical tweets
history = api.get_history(
    handles=["elonmusk", "VitalikButerin"],
    limit=100,
    start_date="2024-01-01T00:00:00Z",
)

for tweet in history.data:
    print(f"{tweet.twitter_handle}: {tweet.body}")

# Add accounts to track
added = api.add_accounts(["newhandle1", "newhandle2"])
print(f"Added {added.summary.succeeded} accounts")

# Remove accounts
removed = api.remove_accounts("oldhandle")
print(f"Removed {removed.summary.succeeded} accounts")
```

## Examples

### Token Alert Bot

```python
import asyncio
from tweetstream_sdk import TweetStreamClient, TweetMeta

async def main():
    client = TweetStreamClient(api_key="your-api-key")

    @client.on("tweet_meta")
    async def on_meta(meta: TweetMeta):
        if not meta.detected:
            return

        # Alert on new token mentions
        for token in meta.detected.tokens:
            if token.chain == "solana" and token.price_usd:
                print(f"[SOLANA] {token.symbol}: ${token.price_usd:.6f}")

        # Alert on CEX listings
        for market in meta.detected.cex:
            print(f"[{market.exchange.value.upper()}] {market.symbol}")

    await client.connect()

asyncio.run(main())
```

### Truth Social Monitor

```python
import asyncio
from tweetstream_sdk import TweetStreamClient, TweetContent, Platform

async def main():
    client = TweetStreamClient(api_key="your-api-key")

    @client.on("tweet")
    async def on_tweet(tweet: TweetContent):
        if tweet.author.platform == Platform.TRUTH_SOCIAL:
            print(f"[Truth Social] @{tweet.author.handle}: {tweet.text}")

    await client.connect()

asyncio.run(main())
```

### Profile Change Tracker

```python
import asyncio
from tweetstream_sdk import TweetStreamClient, ProfileUpdateEvent

async def main():
    client = TweetStreamClient(api_key="your-api-key")

    @client.on("profile_update")
    async def on_profile(event: ProfileUpdateEvent):
        changes = []

        if event.changes.name:
            changes.append(f'name: "{event.changes.name}"')
        if event.changes.bio:
            changes.append(f'bio: "{event.changes.bio}"')
        if event.changes.avatar:
            changes.append("avatar updated")
        if event.changes.handle and event.previous:
            changes.append(
                f"handle: @{event.previous.handle} -> @{event.changes.handle}"
            )

        print(f"@{event.actor.handle} changed: {', '.join(changes)}")

    await client.connect()

asyncio.run(main())
```

## API Reference

### TweetStreamClient

#### Constructor Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `api_key` | `str` | *required* | Your TweetStream API key |
| `base_url` | `str` | `wss://ws.tweetstream.io/ws` | WebSocket endpoint |
| `auto_reconnect` | `bool` | `True` | Auto-reconnect on disconnect |
| `max_reconnect_attempts` | `int \| None` | `None` | Max reconnection attempts (None = unlimited) |
| `reconnect_delay` | `float` | `1.0` | Initial reconnect delay in seconds |
| `max_reconnect_delay` | `float` | `30.0` | Max reconnect delay in seconds |

#### Events

| Event | Payload | Description |
|-------|---------|-------------|
| `connected` | - | Connected to WebSocket |
| `disconnected` | `(code: int, reason: str)` | Disconnected from WebSocket |
| `error` | `Exception` | Connection or parse error |
| `message` | `Envelope` | Raw message envelope |
| `tweet` | `TweetContent` | New tweet |
| `tweet_meta` | `TweetMeta` | Tweet metadata (tokens, etc.) |
| `tweet_update` | `TweetUpdate` | Tweet updated |
| `tweet_delete` | `TweetDelete` | Tweet deleted |
| `profile_update` | `ProfileUpdateEvent` | Profile changed |
| `follow` | `FollowEvent` | Follow event |
| `reconnecting` | `(attempt: int, delay: float)` | Reconnecting |

### TweetStreamApi

#### Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `get_history` | See below | `HistoryResponse` | Fetch historical data |
| `add_accounts` | `accounts: str \| list[str]` | `HandleResponse` | Add accounts to track |
| `remove_accounts` | `accounts: str \| list[str]` | `HandleResponse` | Remove tracked accounts |

#### get_history Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `handles` | `str \| list[str] \| None` | Filter by handles |
| `limit` | `int \| None` | Max results (default: 100, max: 1000) |
| `start_date` | `str \| None` | ISO 8601 start date |
| `end_date` | `str \| None` | ISO 8601 end date |
| `message_type` | `MessageType \| None` | Filter by type (TWEET, PROFILE, FOLLOW) |

## Types

All types are exported as dataclasses with full type hints:

```python
from tweetstream_sdk import (
    TweetContent,
    TweetMeta,
    DetectedToken,
    ProfileUpdateEvent,
    FollowEvent,
    # ... and more
)
```

## Links

- [TweetStream](https://tweetstream.io) - Get your API key
- [Documentation](https://tweetstream.io/docs)
- [TypeScript SDK](https://github.com/tenz-app/tweetstream-ts-sdk)

## License

MIT
