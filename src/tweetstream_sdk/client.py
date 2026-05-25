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

from .parsing import (
    parse_detected_entities,
    parse_follow_event,
    parse_profile_update,
    parse_tweet_content,
    parse_tweet_delete,
    parse_tweet_meta,
    parse_tweet_update,
    parse_twitter_handles_result,
)
from .types import (
    DetectedEntities,
    Envelope,
    FollowEvent,
    ProfileUpdateEvent,
    TweetContent,
    TweetDelete,
    TweetMeta,
    TweetUpdate,
    TwitterHandlesResult,
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


NO_RECONNECT_HTTP_STATUSES = {400, 401, 403, 429}

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


def _extract_http_status(error: Exception) -> int | None:
    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response = getattr(error, "response", None)
    response_status = getattr(response, "status_code", None)
    if isinstance(response_status, int):
        return response_status

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
            - tweet_delete: Tweet deleted (deleted: TweetDelete)
            - profile_update: Profile changed (event: ProfileUpdateEvent)
            - follow: Follow event (event: FollowEvent)
            - twitter_handles_result: Handle-management result (result: TwitterHandlesResult)
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
                http_status = _extract_http_status(e)
                if http_status in NO_RECONNECT_HTTP_STATUSES:
                    self._should_reconnect = False
                    break
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
                case "delete":
                    deleted = self._parse_tweet_delete(payload)
                    await self._emit("tweet_delete", deleted)
                case "profile_update":
                    event = self._parse_profile_update(payload)
                    await self._emit("profile_update", event)
                case "follow":
                    event = self._parse_follow_event(payload)
                    await self._emit("follow", event)
                case "twitter_handles_result":
                    result = self._parse_twitter_handles_result(payload)
                    await self._emit("twitter_handles_result", result)

        except Exception as e:
            await self._emit("error", Exception(f"Failed to parse message: {e}"))

    def _parse_tweet_content(self, data: dict) -> TweetContent:
        return parse_tweet_content(data)

    def _parse_detected_entities(self, data: dict) -> DetectedEntities:
        return parse_detected_entities(data)

    def _parse_tweet_meta(self, data: dict | None) -> TweetMeta | None:
        return parse_tweet_meta(data)

    def _parse_tweet_update(self, data: dict) -> TweetUpdate:
        return parse_tweet_update(data)

    def _parse_tweet_delete(self, data: dict) -> TweetDelete:
        return parse_tweet_delete(data)

    def _parse_profile_update(self, data: dict) -> ProfileUpdateEvent:
        return parse_profile_update(data)

    def _parse_follow_event(self, data: dict) -> FollowEvent:
        return parse_follow_event(data)

    def _parse_twitter_handles_result(self, data: dict) -> TwitterHandlesResult:
        return parse_twitter_handles_result(data)

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket."""
        self._should_reconnect = False
        if self._ws:
            await self._ws.close(1000, "Client disconnect")
            self._ws = None
