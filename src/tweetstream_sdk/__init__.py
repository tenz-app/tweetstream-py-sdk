"""
TweetStream SDK
Real-time Twitter/X and Truth Social streaming API

Example:
    ```python
    import asyncio
    from tweetstream_sdk import TweetStreamClient, TweetStreamApi

    # Real-time streaming
    async def main():
        client = TweetStreamClient(api_key="your-api-key")

        @client.on("tweet")
        async def on_tweet(tweet):
            print(f"@{tweet.author.handle}: {tweet.text}")

        await client.connect()

    asyncio.run(main())

    # REST API
    api = TweetStreamApi(api_key="your-api-key")
    history = api.get_history(handles=["elonmusk"], limit=10)
    ```
"""

from .api import TweetStreamApi, TweetStreamApiError
from .client import TweetStreamClient
from .types import (
    AccountActor,
    CexExchange,
    DetectedCexMarket,
    DetectedEntities,
    DetectedPredictionMarket,
    DetectedToken,
    # Envelope
    Envelope,
    FollowEvent,
    HandleOperationResult,
    HandleOperationState,
    HandleResponse,
    HandleSummary,
    # REST API types
    HistoricalTweet,
    HistoryMetadata,
    HistoryResponse,
    # Media
    Media,
    # Enums
    MessageType,
    MetaSource,
    OcrResult,
    Platform,
    PredictionExchange,
    # Account events
    ProfileChanges,
    ProfileUpdateEvent,
    ReferenceType,
    # Authors
    TweetAuthor,
    # Tweet types
    TweetContent,
    TweetMeta,
    # References
    TweetReference,
    TweetUpdate,
)

__version__ = "1.0.3"
__all__ = [
    # Clients
    "TweetStreamClient",
    "TweetStreamApi",
    "TweetStreamApiError",
    # Enums
    "MessageType",
    "Platform",
    "ReferenceType",
    "MetaSource",
    "CexExchange",
    "PredictionExchange",
    "HandleOperationState",
    # Media
    "Media",
    # Authors
    "TweetAuthor",
    "AccountActor",
    # References
    "TweetReference",
    # Tweet types
    "TweetContent",
    "TweetMeta",
    "TweetUpdate",
    "DetectedToken",
    "DetectedCexMarket",
    "DetectedPredictionMarket",
    "DetectedEntities",
    "OcrResult",
    # Account events
    "ProfileChanges",
    "ProfileUpdateEvent",
    "FollowEvent",
    # Envelope
    "Envelope",
    # REST API types
    "HistoricalTweet",
    "HistoryMetadata",
    "HistoryResponse",
    "HandleOperationResult",
    "HandleSummary",
    "HandleResponse",
]
