import unittest

from tweetstream_sdk import (
    CexExchange,
    MessageType,
    Platform,
    PredictionExchange,
    TweetStreamApi,
    TweetStreamClient,
    __version__,
)


class TweetStreamPublicContractTests(unittest.TestCase):
    def test_package_exports_import_cleanly(self) -> None:
        self.assertEqual(__version__, "1.1.0")

    def test_detected_market_enums_are_parsed(self) -> None:
        client = TweetStreamClient(api_key="test-key")
        entities = client._parse_detected_entities(  # noqa: SLF001
            {
                "cex": [{"exchange": "binance", "sources": ["text"]}],
                "prediction": [{"exchange": "kalshi", "sources": ["ocr"]}],
            }
        )

        self.assertEqual(entities.cex[0].exchange, CexExchange.BINANCE)
        self.assertEqual(entities.prediction[0].exchange, PredictionExchange.KALSHI)

    def test_truth_social_content_fields_are_parsed(self) -> None:
        client = TweetStreamClient(api_key="test-key")
        content = client._parse_tweet_content(  # noqa: SLF001
            {
                "author": {
                    "followersCount": 9800000,
                    "handle": "@realDonaldTrump",
                    "id": "107780257626128384",
                    "location": "Washington, DC",
                    "metrics": {"likes": 10, "tweets": 20},
                    "name": "Donald J. Trump",
                    "platform": "truth_social",
                    "verifiedLabel": {
                        "badge": None,
                        "description": "Government account",
                        "url": None,
                    },
                    "verifiedType": "government",
                },
                "createdAt": 1744156800000,
                "link": "https://truthsocial.com/@realDonaldTrump/posts/116334902567890770",
                "mentions": [{"handle": "@WhiteHouse", "id": "1", "name": "White House"}],
                "text": "Truth Social post",
                "tweetId": "116334902567890770",
                "urls": [
                    {
                        "name": "truthsocial.com",
                        "tco": "https://t.co/example",
                        "url": "https://truthsocial.com",
                    }
                ],
            }
        )

        self.assertEqual(content.author.platform, Platform.TRUTH_SOCIAL)
        self.assertEqual(content.author.followers_count, 9800000)
        self.assertEqual(content.author.metrics.likes, 10)
        self.assertEqual(content.author.verified_type, "government")
        self.assertEqual(content.mentions[0].handle, "@WhiteHouse")
        self.assertEqual(content.urls[0].url, "https://truthsocial.com")

    def test_update_delete_and_control_contracts_are_parsed(self) -> None:
        client = TweetStreamClient(api_key="test-key")

        update = client._parse_tweet_update(  # noqa: SLF001
            {
                "author": {"handle": "@realDonaldTrump", "platform": "truth_social"},
                "mentions": [{"handle": "@WhiteHouse"}],
                "tweetId": "116334902567890770",
                "urls": [{"url": "https://truthsocial.com"}],
            }
        )
        deleted = client._parse_tweet_delete(  # noqa: SLF001
            {"tweetId": "116334902567890770"}
        )
        handle_result = client._parse_twitter_handles_result(  # noqa: SLF001
            {
                "action": "follow",
                "error": None,
                "requestId": "req-1",
                "results": [
                    {
                        "input": "realDonaldTrump",
                        "normalizedHandle": "realDonaldTrump",
                        "state": "added",
                    }
                ],
            }
        )

        self.assertEqual(update.author.platform, Platform.TRUTH_SOCIAL)
        self.assertEqual(update.mentions[0].handle, "@WhiteHouse")
        self.assertEqual(update.urls[0].url, "https://truthsocial.com")
        self.assertEqual(deleted.tweet_id, "116334902567890770")
        self.assertEqual(handle_result.request_id, "req-1")
        self.assertEqual(handle_result.results[0].normalized_handle, "realDonaldTrump")

    def test_history_response_returns_typed_content_and_meta(self) -> None:
        api = TweetStreamApi(api_key="test-key")

        history = api._parse_history_response(  # noqa: SLF001
            {
                "data": [
                    {
                        "body": "Truth Social post",
                        "content": {
                            "author": {
                                "handle": "@realDonaldTrump",
                                "platform": "truth_social",
                            },
                            "createdAt": 1744156800000,
                            "text": "Truth Social post",
                            "tweetId": "116334902567890770",
                        },
                        "link": "https://truthsocial.com/@realDonaldTrump/posts/116334902567890770",
                        "messageType": "TWEET",
                        "meta": {
                            "detected": {"tokens": [{"sources": ["text"], "symbol": "BTC"}]},
                            "tweetId": "116334902567890770",
                        },
                        "receivedTime": "2026-04-09T01:00:00.500Z",
                        "time": "2026-04-09T01:00:00.000Z",
                        "tweetId": "116334902567890770",
                        "twitterHandle": "@realDonaldTrump",
                        "twitterId": "107780257626128384",
                    }
                ],
                "metadata": {"count": 1, "type": "TWEET"},
            }
        )

        row = history.data[0]
        self.assertEqual(history.metadata.type, MessageType.TWEET)
        self.assertEqual(row.content.author.platform, Platform.TRUTH_SOCIAL)
        self.assertEqual(row.meta.detected.tokens[0].symbol, "BTC")


if __name__ == "__main__":
    unittest.main()
