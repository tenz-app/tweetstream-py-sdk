"""
TweetStream SDK Types
Real-time Twitter/X and Truth Social streaming API
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, TypeAlias


class MessageType(str, Enum):
    TWEET = "TWEET"
    PROFILE = "PROFILE"
    FOLLOW = "FOLLOW"


class Platform(str, Enum):
    TWITTER = "twitter"
    TRUTH_SOCIAL = "truth_social"


class ReferenceType(str, Enum):
    REPLY = "reply"
    QUOTE = "quote"
    RETWEET = "retweet"


class MetaSource(str, Enum):
    TEXT = "text"
    OCR = "ocr"


class CexExchange(str, Enum):
    BYBIT = "bybit"
    BINANCE = "binance"
    HYPERLIQUID = "hyperliquid"


class PredictionExchange(str, Enum):
    POLYMARKET = "polymarket"
    KALSHI = "kalshi"


class HandleOperationState(str, Enum):
    ADDED = "added"
    ALREADY_FOLLOWING = "already_following"
    INVALID_INPUT = "invalid_input"
    DUPLICATE = "duplicate"
    NOT_FOUND = "not_found"
    FAILED = "failed"
    REMOVED = "removed"
    NOT_FOLLOWING = "not_following"


MessageOperation: TypeAlias = Literal[
    "content",
    "meta",
    "update",
    "delete",
    "profile_update",
    "follow",
    "auth_ping",
    "auth_pong",
    "twitter_handles_result",
]

EnvelopeType: TypeAlias = Literal["tweet", "account", "control"]
MediaType: TypeAlias = Literal["image", "video", "gif"]


@dataclass
class Media:
    url: str
    type: MediaType | None = None
    thumbnail: str | None = None


@dataclass
class TweetAuthor:
    id: str | None = None
    handle: str | None = None
    name: str | None = None
    profile_image: str | None = None
    platform: Platform | None = None


@dataclass
class AccountActor:
    id: str | None = None
    handle: str | None = None
    name: str | None = None
    profile_image: str | None = None
    platform: Platform | None = None
    bio: str | None = None
    banner: str | None = None
    location: str | None = None
    url: str | None = None
    website_url: str | None = None
    followers_count: int | None = None
    following_count: int | None = None
    verified_type: str | None = None


@dataclass
class TweetReference:
    type: ReferenceType
    tweet_id: str | None = None
    text: str | None = None
    author: TweetAuthor | None = None
    media: list[Media] = field(default_factory=list)


@dataclass
class TweetContent:
    tweet_id: str
    text: str
    created_at: int
    author: TweetAuthor
    link: str | None = None
    media: list[Media] = field(default_factory=list)
    ref: TweetReference | None = None


@dataclass
class DetectedToken:
    sources: list[MetaSource]
    symbol: str | None = None
    name: str | None = None
    contract: str | None = None
    chain: str | None = None
    network_id: int | None = None
    price_usd: float | None = None


@dataclass
class DetectedCexMarket:
    exchange: CexExchange
    sources: list[MetaSource]
    symbol: str | None = None
    base_asset: str | None = None
    quote_asset: str | None = None
    price_usd: float | None = None
    url: str | None = None


@dataclass
class DetectedPredictionMarket:
    exchange: PredictionExchange
    sources: list[MetaSource]
    market_id: str | None = None
    title: str | None = None
    price_usd: float | None = None
    url: str | None = None


@dataclass
class DetectedEntities:
    tokens: list[DetectedToken] = field(default_factory=list)
    cex: list[DetectedCexMarket] = field(default_factory=list)
    prediction: list[DetectedPredictionMarket] = field(default_factory=list)


@dataclass
class OcrResult:
    text: str


@dataclass
class TweetMeta:
    tweet_id: str
    detected: DetectedEntities | None = None
    ocr: OcrResult | None = None


@dataclass
class TweetUpdate:
    tweet_id: str
    text: str | None = None
    media: list[Media] = field(default_factory=list)
    ref: TweetReference | None = None


@dataclass
class TweetDelete:
    tweet_id: str


@dataclass
class ProfileChanges:
    name: str | None = None
    handle: str | None = None
    bio: str | None = None
    avatar: str | None = None
    banner: str | None = None
    location: str | None = None


@dataclass
class ProfileUpdateEvent:
    kind: Literal["PROFILE"]
    event_id: str
    observed_at: int
    actor: AccountActor
    changes: ProfileChanges
    previous: ProfileChanges | None = None


@dataclass
class FollowEvent:
    kind: Literal["FOLLOW"]
    event_id: str
    observed_at: int
    actor: AccountActor
    target: AccountActor


@dataclass
class Envelope:
    v: int
    t: EnvelopeType
    op: MessageOperation
    ts: int
    d: dict
    id: str | None = None


# REST API types


@dataclass
class HistoricalTweet:
    tweet_id: str
    twitter_id: str
    twitter_handle: str | None
    body: str
    link: str
    time: str
    received_time: str
    message_type: MessageType
    content: TweetContent | ProfileUpdateEvent | FollowEvent
    meta: TweetMeta | None = None


@dataclass
class HistoryMetadata:
    count: int
    handle: str | None = None
    handles: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    type: MessageType | None = None


@dataclass
class HistoryResponse:
    data: list[HistoricalTweet]
    metadata: HistoryMetadata


@dataclass
class HandleOperationResult:
    input: str
    state: HandleOperationState
    handle: str | None = None
    normalized_handle: str | None = None
    name: str | None = None
    profile_image: str | None = None
    twitter_id: str | None = None
    message: str | None = None


@dataclass
class HandleSummary:
    total: int
    succeeded: int
    failed: int


@dataclass
class HandleResponse:
    action: Literal["follow", "unfollow"]
    request_id: str | None
    error: str | None
    results: list[HandleOperationResult]
    summary: HandleSummary
