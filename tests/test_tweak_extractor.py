import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from llm_pipeline.models import Review  # noqa: E402
from llm_pipeline.tweak_extractor import TweakExtractor  # noqa: E402


class TestTweakExtractorRanking(unittest.TestCase):
    def setUp(self):
        # rank_reviews does not depend on client/model state.
        self.extractor = object.__new__(TweakExtractor)

    def test_rank_reviews_is_deterministic_and_uses_stable_priority(self):
        reviews = [
            Review(
                text="non-mod-should-be-filtered",
                has_modification=False,
                is_featured=True,
                helpful_count=999,
                rating=5,
            ),
            Review(
                text="regular-a",
                has_modification=True,
                is_featured=False,
                helpful_count=10,
                rating=4,
            ),
            Review(
                text="featured-low",
                has_modification=True,
                is_featured=True,
                helpful_count=1,
                rating=1,
            ),
            Review(
                text="featured-top",
                has_modification=True,
                is_featured=True,
                helpful_count=10,
                rating=5,
            ),
            Review(
                text="regular-b",
                has_modification=True,
                is_featured=False,
                helpful_count=10,
                rating=4,
            ),
            Review(
                text="tie-a",
                has_modification=True,
                is_featured=False,
                helpful_count=0,
                rating=3,
            ),
            Review(
                text="tie-b",
                has_modification=True,
                is_featured=False,
                helpful_count=0,
                rating=3,
            ),
        ]

        ranked_first = self.extractor.rank_reviews(reviews)
        ranked_second = self.extractor.rank_reviews(reviews)

        ranked_texts_first = [review.text for review in ranked_first]
        ranked_texts_second = [review.text for review in ranked_second]

        self.assertEqual(
            ranked_texts_first,
            [
                "featured-top",
                "featured-low",
                "regular-a",
                "regular-b",
                "tie-a",
                "tie-b",
            ],
        )
        self.assertEqual(ranked_texts_first, ranked_texts_second)
        self.assertNotIn("non-mod-should-be-filtered", ranked_texts_first)


if __name__ == "__main__":
    unittest.main()
