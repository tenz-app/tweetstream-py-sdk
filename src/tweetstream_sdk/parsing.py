"""Shared TweetStream wire-format parsing helpers."""

from enum import Enum
from typing import Any, TypeVar

from .types import (
    AccountActor,
    CexExchange,
    DetectedCexMarket,
    DetectedEntities,
    DetectedPredictionMarket,
    DetectedToken,
    FollowEvent,
    HandleOperationResult,
    HandleOperationState,
    Media,
    MetaSource,
    OcrResult,
    Platform,
    PredictionExchange,
    ProfileChanges,
    ProfileUpdateEvent,
    ReferenceType,
    TweetAuthor,
    TweetAuthorMetrics,
    TweetContent,
    TweetDelete,
    TweetMention,
    TweetMeta,
    TweetReference,
    TweetUpdate,
    TweetUrl,
    TweetVerifiedLabel,
    TwitterHandlesResult,
    VerifiedType,
)

EnumType = TypeVar("EnumType", bound=Enum)
VALID_VERIFIED_TYPES = {"blue", "business", "government", "none"}


def parse_enum(enum_cls: type[EnumType], raw_value: Any) -> EnumType | None:
    if raw_value is None:
        return None

    try:
        return enum_cls(raw_value)
    except ValueError:
        return None


def parse_verified_type(value: Any) -> VerifiedType | None:
    if isinstance(value, str) and value in VALID_VERIFIED_TYPES:
        return value
    return None


def parse_author_metrics(data: dict | None) -> TweetAuthorMetrics | None:
    if not data:
        return None

    return TweetAuthorMetrics(
        likes=data.get("likes"),
        tweets=data.get("tweets"),
    )


def parse_verified_label(data: dict | None) -> TweetVerifiedLabel | None:
    if not data:
        return None

    return TweetVerifiedLabel(
        badge=data.get("badge"),
        description=data.get("description", ""),
        url=data.get("url"),
    )


def parse_tweet_author(data: dict) -> TweetAuthor:
    return TweetAuthor(
        banner=data.get("banner"),
        bio=data.get("bio"),
        followers_count=data.get("followersCount"),
        following_count=data.get("followingCount"),
        handle=data.get("handle"),
        id=data.get("id"),
        joined_at=data.get("joinedAt"),
        location=data.get("location"),
        metrics=parse_author_metrics(data.get("metrics")),
        name=data.get("name"),
        platform=parse_enum(Platform, data.get("platform")),
        profile_image=data.get("profileImage"),
        url=data.get("url"),
        verified_label=parse_verified_label(data.get("verifiedLabel")),
        verified_type=parse_verified_type(data.get("verifiedType")),
    )


def parse_account_actor(data: dict) -> AccountActor:
    return AccountActor(
        banner=data.get("banner"),
        bio=data.get("bio"),
        followers_count=data.get("followersCount"),
        following_count=data.get("followingCount"),
        handle=data.get("handle"),
        id=data.get("id"),
        joined_at=data.get("joinedAt"),
        location=data.get("location"),
        metrics=parse_author_metrics(data.get("metrics")),
        name=data.get("name"),
        platform=parse_enum(Platform, data.get("platform")),
        profile_image=data.get("profileImage"),
        url=data.get("url"),
        verified_label=parse_verified_label(data.get("verifiedLabel")),
        verified_type=parse_verified_type(data.get("verifiedType")),
        website_url=data.get("websiteUrl"),
    )


def parse_media(data: list) -> list[Media]:
    return [
        Media(
            url=m.get("url", ""),
            type=m.get("type"),
            thumbnail=m.get("thumbnail"),
        )
        for m in data
    ]


def parse_tweet_mentions(data: list) -> list[TweetMention]:
    return [
        TweetMention(
            handle=m.get("handle"),
            id=m.get("id"),
            name=m.get("name"),
        )
        for m in data
    ]


def parse_tweet_urls(data: list) -> list[TweetUrl]:
    return [
        TweetUrl(
            url=u.get("url", ""),
            name=u.get("name"),
            tco=u.get("tco"),
        )
        for u in data
    ]


def parse_reference(data: dict) -> TweetReference:
    return TweetReference(
        type=parse_enum(ReferenceType, data.get("type")) or ReferenceType.REPLY,
        tweet_id=data.get("tweetId"),
        text=data.get("text"),
        author=parse_tweet_author(data.get("author", {})) if data.get("author") else None,
        media=parse_media(data.get("media", [])),
    )


def parse_tweet_content(data: dict) -> TweetContent:
    return TweetContent(
        tweet_id=data.get("tweetId", ""),
        text=data.get("text", ""),
        created_at=data.get("createdAt", 0),
        author=parse_tweet_author(data.get("author", {})),
        link=data.get("link"),
        media=parse_media(data.get("media", [])),
        mentions=parse_tweet_mentions(data.get("mentions", [])),
        ref=parse_reference(data["ref"]) if data.get("ref") else None,
        urls=parse_tweet_urls(data.get("urls", [])),
    )


def parse_detected_entities(data: dict) -> DetectedEntities:
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
            exchange=parse_enum(CexExchange, c.get("exchange")) or CexExchange.BINANCE,
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
                parse_enum(PredictionExchange, p.get("exchange"))
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


def parse_tweet_meta(data: dict | None) -> TweetMeta | None:
    if data is None:
        return None

    detected = None
    if d := data.get("detected"):
        detected = parse_detected_entities(d)

    ocr = None
    if o := data.get("ocr"):
        ocr = OcrResult(text=o.get("text", ""))

    return TweetMeta(
        tweet_id=data.get("tweetId", ""),
        detected=detected,
        ocr=ocr,
    )


def parse_tweet_update(data: dict) -> TweetUpdate:
    return TweetUpdate(
        tweet_id=data.get("tweetId", ""),
        author=parse_tweet_author(data["author"]) if data.get("author") else None,
        text=data.get("text"),
        media=parse_media(data.get("media", [])),
        mentions=parse_tweet_mentions(data.get("mentions", [])),
        ref=parse_reference(data["ref"]) if data.get("ref") else None,
        urls=parse_tweet_urls(data.get("urls", [])),
    )


def parse_tweet_delete(data: dict) -> TweetDelete:
    return TweetDelete(tweet_id=data.get("tweetId", ""))


def parse_profile_changes(data: dict) -> ProfileChanges:
    return ProfileChanges(
        name=data.get("name"),
        handle=data.get("handle"),
        bio=data.get("bio"),
        avatar=data.get("avatar"),
        banner=data.get("banner"),
        location=data.get("location"),
    )


def parse_profile_update(data: dict) -> ProfileUpdateEvent:
    return ProfileUpdateEvent(
        kind="PROFILE",
        event_id=data.get("eventId", ""),
        observed_at=data.get("observedAt", 0),
        actor=parse_account_actor(data.get("actor", {})),
        changes=parse_profile_changes(data.get("changes", {})),
        previous=parse_profile_changes(data["previous"]) if data.get("previous") else None,
    )


def parse_follow_event(data: dict) -> FollowEvent:
    return FollowEvent(
        kind="FOLLOW",
        event_id=data.get("eventId", ""),
        observed_at=data.get("observedAt", 0),
        actor=parse_account_actor(data.get("actor", {})),
        target=parse_account_actor(data.get("target", {})),
    )


def parse_handle_operation_result(data: dict) -> HandleOperationResult:
    return HandleOperationResult(
        input=data.get("input", ""),
        state=parse_enum(HandleOperationState, data.get("state")) or HandleOperationState.FAILED,
        handle=data.get("handle"),
        normalized_handle=data.get("normalizedHandle"),
        name=data.get("name"),
        profile_image=data.get("profileImage"),
        twitter_id=data.get("twitterId"),
        message=data.get("message"),
    )


def parse_twitter_handles_result(data: dict) -> TwitterHandlesResult:
    return TwitterHandlesResult(
        action=data.get("action", "follow"),
        request_id=data.get("requestId"),
        error=data.get("error"),
        results=[parse_handle_operation_result(r) for r in data.get("results", [])],
    )
