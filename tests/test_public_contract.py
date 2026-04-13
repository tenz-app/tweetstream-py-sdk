import unittest

from tweetstream_sdk import (
    CexExchange,
    PredictionExchange,
    TweetStreamClient,
    __version__,
)


class TweetStreamPublicContractTests(unittest.TestCase):
    def test_package_exports_import_cleanly(self) -> None:
        self.assertEqual(__version__, "1.0.3")

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


if __name__ == "__main__":
    unittest.main()
