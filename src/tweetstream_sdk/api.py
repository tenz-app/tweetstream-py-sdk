"""
TweetStream REST API Client
Historical data and account management
"""

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from .types import (
    HandleOperationResult,
    HandleOperationState,
    HandleResponse,
    HandleSummary,
    HistoricalTweet,
    HistoryMetadata,
    HistoryResponse,
    MessageType,
)

DEFAULT_API_URL = "https://api.tweetstream.io"


class TweetStreamApiError(Exception):
    """API error with status code and details."""

    def __init__(self, message: str, status: int, details: Any = None):
        super().__init__(message)
        self.status = status
        self.details = details


@dataclass
class TweetStreamApi:
    """
    TweetStream REST API client for historical data and account management.

    Example:
        ```python
        api = TweetStreamApi(api_key="your-api-key")

        # Get historical tweets
        history = api.get_history(handles=["elonmusk"], limit=10)
        for tweet in history.data:
            print(f"{tweet.twitter_handle}: {tweet.body}")

        # Add accounts to track
        result = api.add_accounts(["newhandle"])
        print(f"Added {result.summary.succeeded} accounts")
        ```
    """

    api_key: str
    base_url: str = DEFAULT_API_URL

    def __post_init__(self):
        if not self.api_key:
            raise ValueError("api_key is required")

    def get_history(
        self,
        *,
        handles: str | list[str] | None = None,
        limit: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        message_type: MessageType | None = None,
    ) -> HistoryResponse:
        """
        Fetch historical tweets, profile updates, or follow events.

        Args:
            handles: Filter by handle(s)
            limit: Max results (default: 100, max: 1000)
            start_date: ISO 8601 start date
            end_date: ISO 8601 end date
            message_type: Filter by type (TWEET, PROFILE, FOLLOW)

        Returns:
            HistoryResponse with data and metadata

        Example:
            ```python
            # Get recent tweets from specific handles
            tweets = api.get_history(
                handles=["elonmusk", "VitalikButerin"],
                limit=50
            )

            # Get profile updates from the last hour
            from datetime import datetime, timedelta
            profiles = api.get_history(
                message_type=MessageType.PROFILE,
                start_date=(datetime.now() - timedelta(hours=1)).isoformat()
            )
            ```
        """
        params: list[tuple[str, str]] = []

        if handles:
            handle_list = [handles] if isinstance(handles, str) else handles
            for h in handle_list:
                params.append(("handles", h))

        if limit is not None:
            params.append(("limit", str(limit)))
        if start_date:
            params.append(("startDate", start_date))
        if end_date:
            params.append(("endDate", end_date))
        if message_type:
            params.append(("type", message_type.value))

        url = f"{self.base_url}/api/history"
        if params:
            url += "?" + urlencode(params)

        data = self._request("GET", url)
        return self._parse_history_response(data)

    def add_accounts(self, accounts: str | list[str]) -> HandleResponse:
        """
        Add Twitter/X accounts to track.

        Args:
            accounts: Single handle or list of handles to add

        Returns:
            HandleResponse with results for each account

        Example:
            ```python
            # Add a single account
            result = api.add_accounts("elonmusk")

            # Add multiple accounts
            result = api.add_accounts(["elonmusk", "VitalikButerin"])
            print(f"Added {result.summary.succeeded} of {result.summary.total}")
            ```
        """
        url = f"{self.base_url}/api/add-account"
        body = {"accounts": accounts}
        data = self._request("POST", url, body)
        return self._parse_handle_response(data)

    def remove_accounts(self, accounts: str | list[str]) -> HandleResponse:
        """
        Remove Twitter/X accounts from tracking.

        Args:
            accounts: Single handle or list of handles to remove

        Returns:
            HandleResponse with results for each account

        Example:
            ```python
            # Remove a single account
            result = api.remove_accounts("oldhandle")

            # Remove multiple accounts
            result = api.remove_accounts(["handle1", "handle2"])
            ```
        """
        url = f"{self.base_url}/api/remove-account"
        body = {"accounts": accounts}
        data = self._request("DELETE", url, body)
        return self._parse_handle_response(data)

    def _request(
        self, method: str, url: str, body: dict | None = None
    ) -> dict:
        """Make an HTTP request."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        request_body = json.dumps(body).encode("utf-8") if body else None
        req = Request(url, data=request_body, headers=headers, method=method)

        try:
            with urlopen(req) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as e:
            try:
                error_body = json.loads(e.read().decode("utf-8"))
                message = error_body.get("error") or error_body.get("message") or str(e)
                details = error_body.get("details")
            except Exception:
                message = f"HTTP {e.code}: {e.reason}"
                details = None
            raise TweetStreamApiError(message, e.code, details) from e

    def _parse_history_response(self, data: dict) -> HistoryResponse:
        """Parse history API response."""
        metadata = data.get("metadata", {})

        msg_type = None
        if t := metadata.get("type"):
            msg_type = MessageType(t)

        return HistoryResponse(
            data=[self._parse_historical_tweet(t) for t in data.get("data", [])],
            metadata=HistoryMetadata(
                count=metadata.get("count", 0),
                handle=metadata.get("handle"),
                handles=metadata.get("handles"),
                start_date=metadata.get("startDate"),
                end_date=metadata.get("endDate"),
                type=msg_type,
            ),
        )

    def _parse_historical_tweet(self, data: dict) -> HistoricalTweet:
        """Parse a historical tweet from API response."""
        # Content is already parsed by server, just wrap it
        content = data.get("content", {})
        meta = data.get("meta")

        return HistoricalTweet(
            tweet_id=data.get("tweetId", ""),
            twitter_id=data.get("twitterId", ""),
            twitter_handle=data.get("twitterHandle"),
            body=data.get("body", ""),
            link=data.get("link", ""),
            time=data.get("time", ""),
            received_time=data.get("receivedTime", ""),
            message_type=MessageType(data.get("messageType", "TWEET")),
            content=content,  # type: ignore - simplified for API
            meta=meta,  # type: ignore - simplified for API
        )

    def _parse_handle_response(self, data: dict) -> HandleResponse:
        """Parse handle management API response."""
        summary = data.get("summary", {})

        return HandleResponse(
            action=data.get("action", "follow"),
            request_id=data.get("requestId"),
            error=data.get("error"),
            results=[
                HandleOperationResult(
                    input=r.get("input", ""),
                    state=HandleOperationState(r.get("state", "failed")),
                    handle=r.get("handle"),
                    normalized_handle=r.get("normalizedHandle"),
                    name=r.get("name"),
                    profile_image=r.get("profileImage"),
                    twitter_id=r.get("twitterId"),
                    message=r.get("message"),
                )
                for r in data.get("results", [])
            ],
            summary=HandleSummary(
                total=summary.get("total", 0),
                succeeded=summary.get("succeeded", 0),
                failed=summary.get("failed", 0),
            ),
        )
