"""
Token Detection Alert Example

Monitors tweets for cryptocurrency token mentions and displays alerts.

Run: python examples/token_alerts.py
"""

import asyncio
import os
import signal
from contextlib import suppress

from tweetstream_sdk import (
    DetectedCexMarket,
    DetectedToken,
    TweetContent,
    TweetMeta,
    TweetStreamClient,
)

# Store recent tweets to correlate with metadata
recent_tweets: dict[str, tuple[str, str]] = {}


async def main():
    api_key = os.environ.get("TWEETSTREAM_API_KEY")
    if not api_key:
        print("Please set TWEETSTREAM_API_KEY environment variable")
        return

    client = TweetStreamClient(api_key=api_key)

    @client.on("tweet")
    async def on_tweet(tweet: TweetContent):
        recent_tweets[tweet.tweet_id] = (
            tweet.author.handle or "unknown",
            tweet.text,
        )

        # Cleanup old entries
        if len(recent_tweets) > 1000:
            oldest_key = next(iter(recent_tweets))
            del recent_tweets[oldest_key]

    @client.on("tweet_meta")
    async def on_meta(meta: TweetMeta):
        tweet_info = recent_tweets.get(meta.tweet_id)
        handle = tweet_info[0] if tweet_info else "unknown"

        if not meta.detected:
            return

        # Check for onchain tokens
        for token in meta.detected.tokens:
            print_token_alert(handle, token)

        # Check for CEX mentions
        for market in meta.detected.cex:
            print_cex_alert(handle, market)

        # Check for prediction markets
        for prediction in meta.detected.prediction:
            title = prediction.title or prediction.market_id
            print(f"[PREDICTION] @{handle} mentioned {prediction.exchange.value}: {title}")

    @client.on("connected")
    async def on_connected():
        print("Connected! Monitoring for token mentions...\n")

    @client.on("error")
    async def on_error(error: Exception):
        print(f"Error: {error}")

    # Handle graceful shutdown
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def handle_signal():
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    connect_task = asyncio.create_task(client.connect())
    await stop_event.wait()
    await client.disconnect()
    connect_task.cancel()

    with suppress(asyncio.CancelledError):
        await connect_task


def print_token_alert(handle: str, token: DetectedToken) -> None:
    chain = (token.chain or "UNKNOWN").upper()
    symbol = token.symbol or "???"
    price = f"${token.price_usd:.6f}" if token.price_usd else "N/A"
    source = ", ".join(s.value for s in token.sources)

    print(f"[{chain}] @{handle} mentioned {symbol} | Price: {price} | Source: {source}")

    if token.contract:
        print(f"         Contract: {token.contract}")


def print_cex_alert(handle: str, market: DetectedCexMarket) -> None:
    exchange = market.exchange.value.upper()
    pair = market.symbol or f"{market.base_asset}/{market.quote_asset}"
    price = f"${market.price_usd:.2f}" if market.price_usd else "N/A"

    print(f"[{exchange}] @{handle} mentioned {pair} | Price: {price}")


if __name__ == "__main__":
    asyncio.run(main())
