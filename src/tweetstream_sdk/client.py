"""
TweetStream WebSocket Client
Real-time Twitter/X and Truth Social streaming
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

from .types import (
    AccountActor,
    CexExchange,
    DetectedCexMarket,
    DetectedEntities,
    DetectedPredictionMarket,
    DetectedToken,
    Envelope,
    FollowEvent,
    Media,
    MetaSource,
    OcrResult,
    Platform,
    PredictionExchange,
    ProfileChanges,
    ProfileUpdateEvent,
    ReferenceType,
    TweetAuthor,
    TweetContent,
    TweetMeta,
    TweetReference,
    TweetUpdate,
)

logger = logging.getLogger(__name__)

DEFAULT_WS_URL = "wss://ws.tweetstream.io/ws"
DEFAULT_RECONNECT_DELAY = 1.0
DEFAULT_MAX_RECONNECT_DELAY = 30.0
DEFAULT_MAX_RECONNECT_ATTEMPTS = None  # Unlimited


class CloseCode(Enum):
    """WebSocket close codes"""

    NORMAL = 1000
    SERVER_SHUTDOWN = 1012
    INVALID_API_KEY = 4001
    PLAN_ISSUE = 4003
    CONNECTION_LIMIT = 4029


# Close codes that should not trigger reconnection
NO_RECONNECT_CODES = {
    CloseCode.NORMAL.value,
    CloseCode.INVALID_API_KEY.value,
    CloseCode.PLAN_ISSUE.value,
    CloseCode.CONNECTION_LIMIT.value,
}

# Close codes for immediate reconnect (server restart/deploy)
IMMEDIATE_RECONNECT_CODES = {CloseCode.SERVER_SHUTDOWN.value}


EventCallback = Callable[..., Awaitable[None] | None]


def _parse_enum(enum_cls: type[Enum], raw_value: Any) -> Enum | None:
    if raw_value is None:
        return None

    try:
        return enum_cls(raw_value)
    except ValueError:
        return None


@dataclass
class TweetStreamOptions:
    api_key: str
    base_url: str = DEFAULT_WS_URL
    auto_reconnect: bool = True
    max_reconnect_attempts: int | None = DEFAULT_MAX_RECONNECT_ATTEMPTS
    reconnect_delay: float = DEFAULT_RECONNECT_DELAY
    max_reconnect_delay: float = DEFAULT_MAX_RECONNECT_DELAY


@dataclass
class TweetStreamClient:
    """
    TweetStream WebSocket client for real-time streaming.

    Example:
        ```python
        async def main():
            client = TweetStreamClient(api_key="your-api-key")

            @client.on("tweet")
            async def on_tweet(tweet: TweetContent):
                print(f"@{tweet.author.handle}: {tweet.text}")

            await client.connect()
        ```
    """

    options: TweetStreamOptions
    _ws: ClientConnection | None = field(default=None, init=False, repr=False)
    _reconnect_attempts: int = field(default=0, init=False, repr=False)
    _should_reconnect: bool = field(default=True, init=False, repr=False)
    _listeners: dict[str, list[EventCallback]] = field(
        default_factory=dict, init=False, repr=False
    )

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_WS_URL,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int | None = DEFAULT_MAX_RECONNECT_ATTEMPTS,
        reconnect_delay: float = DEFAULT_RECONNECT_DELAY,
        max_reconnect_delay: float = DEFAULT_MAX_RECONNECT_DELAY,
    ):
        if not api_key:
            raise ValueError("api_key is required")

        self.options = TweetStreamOptions(
            api_key=api_key,
            base_url=base_url,
            auto_reconnect=auto_reconnect,
            max_reconnect_attempts=max_reconnect_attempts,
            reconnect_delay=reconnect_delay,
            max_reconnect_delay=max_reconnect_delay,
        )
        self._ws = None
        self._reconnect_attempts = 0
        self._should_reconnect = True
        self._listeners = {}

    def on(self, event: str) -> Callable[[EventCallback], EventCallback]:
        """
        Decorator to register an event listener.

        Events:
            - connected: Connection established
            - disconnected: Connection closed (code: int, reason: str)
            - error: Error occurred (error: Exception)
            - message: Raw message received (envelope: Envelope)
            - tweet: New tweet (content: TweetContent)
            - tweet_meta: Tweet metadata (meta: TweetMeta)
            - tweet_update: Tweet updated (update: TweetUpdate)
            - profile_update: Profile changed (event: ProfileUpdateEvent)
            - follow: Follow event (event: FollowEvent)
            - reconnecting: Reconnecting (attempt: int, delay: float)

        Example:
            ```python
            @client.on("tweet")
            async def on_tweet(tweet: TweetContent):
                print(tweet.text)
            ```
        """

        def decorator(callback: EventCallback) -> EventCallback:
            if event not in self._listeners:
                self._listeners[event] = []
            self._listeners[event].append(callback)
            return callback

        return decorator

    def off(self, event: str, callback: EventCallback) -> None:
        """Remove an event listener."""
        if event in self._listeners:
            self._listeners[event] = [
                cb for cb in self._listeners[event] if cb != callback
            ]

    async def _emit(self, event: str, *args: Any) -> None:
        """Emit an event to all listeners."""
        if event not in self._listeners:
            return

        for callback in self._listeners[event]:
            try:
                result = callback(*args)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.exception(f"Error in {event} listener: {e}")

    @property
    def connected(self) -> bool:
        """Check if the client is connected."""
        return self._ws is not None and self._ws.state.name == "OPEN"

    async def connect(self) -> None:
        """
        Connect to the TweetStream WebSocket and start receiving messages.
        This method will block until disconnect() is called or an unrecoverable error occurs.
        """
        self._should_reconnect = True
        await self._connect_loop()

    async def _connect_loop(self) -> None:
        """Main connection loop with reconnection logic."""
        while self._should_reconnect:
            try:
                await self._connect_once()
            except Exception as e:
                await self._emit("error", e)
                if not self._should_reconnect:
                    break
                await self._handle_reconnect(1006)

    async def _connect_once(self) -> None:
        """Establish a single connection and process messages."""
        subprotocols = [
            f"tweetstream.auth.token.{self.options.api_key}",
            "tweetstream.v1",
        ]

        try:
            async with websockets.connect(
                self.options.base_url,
                subprotocols=subprotocols,
            ) as ws:
                self._ws = ws
                self._reconnect_attempts = 0
                await self._emit("connected")

                async for message in ws:
                    await self._handle_message(message)
        except websockets.ConnectionClosedOK as e:
            await self._emit("disconnected", e.code, e.reason or "Connection closed")
            if e.code in NO_RECONNECT_CODES:
                self._should_reconnect = False
        except websockets.ConnectionClosedError as e:
            await self._emit("disconnected", e.code, e.reason or "Connection error")
            await self._handle_reconnect(e.code)
        finally:
            self._ws = None

    async def _handle_reconnect(self, close_code: int) -> None:
        """Handle reconnection logic."""
        if not self.options.auto_reconnect or not self._should_reconnect:
            return

        if close_code in NO_RECONNECT_CODES:
            self._should_reconnect = False
            return

        max_attempts = self.options.max_reconnect_attempts
        if max_attempts is not None and self._reconnect_attempts >= max_attempts:
            await self._emit("error", Exception("Max reconnection attempts reached"))
            self._should_reconnect = False
            return

        # Calculate delay with exponential backoff
        if close_code in IMMEDIATE_RECONNECT_CODES:
            delay = 0.1
        else:
            delay = min(
                self.options.reconnect_delay * (2**self._reconnect_attempts),
                self.options.max_reconnect_delay,
            )
            # Add jitter
            import random

            delay += random.uniform(0, 1)

        self._reconnect_attempts += 1
        await self._emit("reconnecting", self._reconnect_attempts, delay)
        await asyncio.sleep(delay)

    async def _handle_message(self, data: str | bytes) -> None:
        """Parse and dispatch a message."""
        try:
            text = data if isinstance(data, str) else data.decode("utf-8")
            raw = json.loads(text)

            envelope = Envelope(
                v=raw.get("v", 1),
                t=raw.get("t", "tweet"),
                op=raw.get("op", "content"),
                ts=raw.get("ts", 0),
                d=raw.get("d", {}),
                id=raw.get("id"),
            )

            await self._emit("message", envelope)

            # Dispatch typed events
            payload = envelope.d
            match envelope.op:
                case "content":
                    content = self._parse_tweet_content(payload)
                    await self._emit("tweet", content)
                case "meta":
                    meta = self._parse_tweet_meta(payload)
                    await self._emit("tweet_meta", meta)
                case "update":
                    update = self._parse_tweet_update(payload)
                    await self._emit("tweet_update", update)
                case "profile_update":
                    event = self._parse_profile_update(payload)
                    await self._emit("profile_update", event)
                case "follow":
                    event = self._parse_follow_event(payload)
                    await self._emit("follow", event)

        except Exception as e:
            await self._emit("error", Exception(f"Failed to parse message: {e}"))

    def _parse_tweet_author(self, data: dict) -> TweetAuthor:
        return TweetAuthor(
            id=data.get("id"),
            handle=data.get("handle"),
            name=data.get("name"),
            profile_image=data.get("profileImage"),
            platform=_parse_enum(Platform, data.get("platform")),
        )

    def _parse_account_actor(self, data: dict) -> AccountActor:
        return AccountActor(
            id=data.get("id"),
            handle=data.get("handle"),
            name=data.get("name"),
            profile_image=data.get("profileImage"),
            platform=_parse_enum(Platform, data.get("platform")),
            bio=data.get("bio"),
            banner=data.get("banner"),
            location=data.get("location"),
            url=data.get("url"),
            website_url=data.get("websiteUrl"),
            followers_count=data.get("followersCount"),
            following_count=data.get("followingCount"),
            verified_type=data.get("verifiedType"),
        )

    def _parse_media(self, data: list) -> list[Media]:
        return [
            Media(
                url=m.get("url", ""),
                type=m.get("type"),
                thumbnail=m.get("thumbnail"),
            )
            for m in data
        ]

    def _parse_reference(self, data: dict) -> TweetReference:
        return TweetReference(
            type=ReferenceType(data.get("type", "reply")),
            tweet_id=data.get("tweetId"),
            text=data.get("text"),
            author=self._parse_tweet_author(data.get("author", {}))
            if data.get("author")
            else None,
            media=self._parse_media(data.get("media", [])),
        )

    def _parse_tweet_content(self, data: dict) -> TweetContent:
        return TweetContent(
            tweet_id=data.get("tweetId", ""),
            text=data.get("text", ""),
            created_at=data.get("createdAt", 0),
            author=self._parse_tweet_author(data.get("author", {})),
            link=data.get("link"),
            media=self._parse_media(data.get("media", [])),
            ref=self._parse_reference(data["ref"]) if data.get("ref") else None,
        )

    def _parse_detected_entities(self, data: dict) -> DetectedEntities:
        tokens = [
            DetectedToken(
                sources=[MetaSource(s) for s in t.get("sources", [])],
                symbol=t.get("symbol"),
                name=t.get("name"),
                contract=t.get("contract"),
                chain=t.get("chain"),
                network_id=t.get("networkId"),
                price_usd=t.get("priceUsd"),
            )
            for t in data.get("tokens", [])
        ]

        cex = [
            DetectedCexMarket(
                exchange=(
                    _parse_enum(CexExchange, c.get("exchange")) or CexExchange.BINANCE
                ),
                sources=[MetaSource(s) for s in c.get("sources", [])],
                symbol=c.get("symbol"),
                base_asset=c.get("baseAsset"),
                quote_asset=c.get("quoteAsset"),
                price_usd=c.get("priceUsd"),
                url=c.get("url"),
            )
            for c in data.get("cex", [])
        ]

        prediction = [
            DetectedPredictionMarket(
                exchange=(
                    _parse_enum(PredictionExchange, p.get("exchange"))
                    or PredictionExchange.POLYMARKET
                ),
                sources=[MetaSource(s) for s in p.get("sources", [])],
                market_id=p.get("marketId"),
                title=p.get("title"),
                price_usd=p.get("priceUsd"),
                url=p.get("url"),
            )
            for p in data.get("prediction", [])
        ]

        return DetectedEntities(tokens=tokens, cex=cex, prediction=prediction)

    def _parse_tweet_meta(self, data: dict) -> TweetMeta:
        detected = None
        if d := data.get("detected"):
            detected = self._parse_detected_entities(d)

        ocr = None
        if o := data.get("ocr"):
            ocr = OcrResult(text=o.get("text", ""))

        return TweetMeta(
            tweet_id=data.get("tweetId", ""),
            detected=detected,
            ocr=ocr,
        )

    def _parse_tweet_update(self, data: dict) -> TweetUpdate:
        return TweetUpdate(
            tweet_id=data.get("tweetId", ""),
            text=data.get("text"),
            media=self._parse_media(data.get("media", [])),
            ref=self._parse_reference(data["ref"]) if data.get("ref") else None,
        )

    def _parse_profile_changes(self, data: dict) -> ProfileChanges:
        return ProfileChanges(
            name=data.get("name"),
            handle=data.get("handle"),
            bio=data.get("bio"),
            avatar=data.get("avatar"),
            banner=data.get("banner"),
            location=data.get("location"),
        )

    def _parse_profile_update(self, data: dict) -> ProfileUpdateEvent:
        return ProfileUpdateEvent(
            kind="PROFILE",
            event_id=data.get("eventId", ""),
            observed_at=data.get("observedAt", 0),
            actor=self._parse_account_actor(data.get("actor", {})),
            changes=self._parse_profile_changes(data.get("changes", {})),
            previous=self._parse_profile_changes(data["previous"])
            if data.get("previous")
            else None,
        )

    def _parse_follow_event(self, data: dict) -> FollowEvent:
        return FollowEvent(
            kind="FOLLOW",
            event_id=data.get("eventId", ""),
            observed_at=data.get("observedAt", 0),
            actor=self._parse_account_actor(data.get("actor", {})),
            target=self._parse_account_actor(data.get("target", {})),
        )

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket."""
        self._should_reconnect = False
        if self._ws:
            await self._ws.close(1000, "Client disconnect")
            self._ws = None
