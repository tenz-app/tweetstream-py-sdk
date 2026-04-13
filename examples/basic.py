"""
Basic TweetStream Example

Run: python examples/basic.py
"""

import asyncio
import os
import signal
from contextlib import suppress

from tweetstream_sdk import (
    FollowEvent,
    Platform,
    ProfileUpdateEvent,
    TweetContent,
    TweetMeta,
    TweetStreamClient,
)


async def main():
    api_key = os.environ.get("TWEETSTREAM_API_KEY")
    if not api_key:
        print("Please set TWEETSTREAM_API_KEY environment variable")
        return

    client = TweetStreamClient(api_key=api_key)

    @client.on("connected")
    async def on_connected():
        print("Connected to TweetStream!")

    @client.on("tweet")
    async def on_tweet(tweet: TweetContent):
        platform = "[Truth]" if tweet.author.platform == Platform.TRUTH_SOCIAL else "[X]"
        text = tweet.text[:100] + "..." if len(tweet.text) > 100 else tweet.text
        print(f"{platform} @{tweet.author.handle}: {text}")

    @client.on("tweet_meta")
    async def on_meta(meta: TweetMeta):
        if meta.detected and meta.detected.tokens:
            symbols = ", ".join(t.symbol or "?" for t in meta.detected.tokens)
            print(f"  Tokens: {symbols}")

    @client.on("profile_update")
    async def on_profile(event: ProfileUpdateEvent):
        print(f"[Profile] @{event.actor.handle} updated their profile")

    @client.on("follow")
    async def on_follow(event: FollowEvent):
        print(f"[Follow] @{event.actor.handle} -> @{event.target.handle}")

    @client.on("disconnected")
    async def on_disconnected(code: int, reason: str):
        print(f"Disconnected: {code} - {reason}")

    @client.on("reconnecting")
    async def on_reconnecting(attempt: int, delay: float):
        print(f"Reconnecting (attempt {attempt}) in {delay:.1f}s...")

    @client.on("error")
    async def on_error(error: Exception):
        print(f"Error: {error}")

    # Handle graceful shutdown
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def handle_signal():
        print("\nDisconnecting...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    print("Connecting to TweetStream...")

    # Run until stopped
    connect_task = asyncio.create_task(client.connect())

    await stop_event.wait()
    await client.disconnect()
    connect_task.cancel()

    with suppress(asyncio.CancelledError):
        await connect_task


if __name__ == "__main__":
    asyncio.run(main())
