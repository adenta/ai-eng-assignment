"""
Step 1: Tweak Extraction & Parsing

This module extracts structured modifications from review text using LLM processing.
It converts natural language descriptions of recipe changes into structured
ModificationObject instances.
"""

import json
import os
from typing import Optional

from loguru import logger
from openai import OpenAI
from pydantic import ValidationError

from .models import ModificationObject, Recipe, Review
from .prompts import build_simple_prompt


class TweakExtractor:
    """Extracts structured modifications from review text using LLM processing."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        """
        Initialize the TweakExtractor.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: OpenAI model to use for extraction
        """
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model
        logger.info(f"Initialized TweakExtractor with model: {model}")

    def extract_modification(
        self,
        review: Review,
        recipe: Recipe,
        max_retries: int = 2,
    ) -> Optional[ModificationObject]:
        """
        Extract a structured modification from a review.

        Args:
            review: Review object containing modification text
            recipe: Original recipe being modified
            max_retries: Number of retry attempts if parsing fails

        Returns:
            ModificationObject if extraction successful, None otherwise
        """
        if not review.has_modification:
            logger.warning("Review has no modification flag set")
            return None

        # Build the prompt - use simple prompt to avoid format string issues
        prompt = build_simple_prompt(
            review.text, recipe.title, recipe.ingredients, recipe.instructions
        )

        logger.debug(
            "Extracting modification from review: {}...".format(review.text[:100])
        )

        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.1,  # Low temperature for consistent extractions
                    max_tokens=1000,
                )

                raw_output = response.choices[0].message.content
                logger.debug(f"LLM raw output: {raw_output}")

                # Check if we got a response
                if not raw_output:
                    logger.warning(f"Attempt {attempt + 1}: Empty response from LLM")
                    continue

                # Parse and validate the JSON response
                modification_data = json.loads(raw_output)
                modification = ModificationObject(**modification_data)

                logger.info(
                    f"Successfully extracted {modification.modification_type} "
                    f"modification with {len(modification.edits)} edits"
                )
                return modification

            except json.JSONDecodeError as e:
                logger.warning(f"Attempt {attempt + 1}: Failed to parse JSON: {e}")
                if attempt == max_retries:
                    logger.error(f"Max retries reached. Raw output: {raw_output}")

            except ValidationError as e:
                logger.warning(f"Attempt {attempt + 1}: Validation error: {e}")
                if attempt == max_retries:
                    logger.error(
                        f"Max retries reached. Invalid data: {modification_data}"
                    )

            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: Unexpected error: {e}")
                if attempt == max_retries:
                    return None

        return None

    def rank_reviews(self, reviews: list[Review]) -> list[Review]:
        """
        Return modification-bearing reviews in a deterministic priority order.

        Ranking criteria (descending priority):
            1. is_featured  (True before False)
            2. helpful_count (higher is better)
            3. rating        (higher is better, None treated as 0)
            4. original index (stable tie-breaker — preserves input order)

        Args:
            reviews: Full list of Review objects

        Returns:
            Sorted list containing only reviews where has_modification is True
        """
        candidates = [r for r in reviews if r.has_modification]
        candidates.sort(
            key=lambda r: (
                r.is_featured,          # True > False
                r.helpful_count,
                r.rating if r.rating is not None else 0,
            ),
            reverse=True,
        )
        return candidates

    def extract_top_k_modifications(
        self,
        reviews: list[Review],
        recipe: Recipe,
        top_k: int = 3,
    ) -> list[tuple[ModificationObject, Review]]:
        """
        Extract modifications from the top-K ranked reviews deterministically.

        Reviews are ranked by: is_featured desc → helpful_count desc →
        rating desc → original index asc.  No randomness is used, so the
        same input always produces the same selected reviews and output.

        Args:
            reviews: List of Review objects (may include both featured and plain)
            recipe:  Original recipe being modified
            top_k:   Maximum number of reviews to process

        Returns:
            List of (ModificationObject, source_Review) pairs for each review
            that produced a valid extraction (length ≤ top_k)
        """
        ranked = self.rank_reviews(reviews)

        if not ranked:
            logger.warning("No reviews with modifications found")
            return []

        selected = ranked[:top_k]
        logger.info(
            f"Selected {len(selected)} review(s) for extraction "
            f"(top_k={top_k}, {sum(r.is_featured for r in selected)} featured)"
        )

        results: list[tuple[ModificationObject, Review]] = []
        for i, review in enumerate(selected, start=1):
            logger.info(
                f"Extracting modification {i}/{len(selected)}: "
                f"featured={review.is_featured}, rating={review.rating}, "
                f"text={review.text[:80]}..."
            )
            modification = self.extract_modification(review, recipe)
            if modification:
                results.append((modification, review))
            else:
                logger.warning(f"Skipping review {i} — extraction returned None")

        logger.info(
            f"Successfully extracted {len(results)}/{len(selected)} modification(s)"
        )
        return results

    def test_extraction(
        self, review_text: str, recipe_data: dict
    ) -> Optional[ModificationObject]:
        """
        Test extraction with raw text and recipe data.

        Args:
            review_text: Raw review text
            recipe_data: Raw recipe dictionary

        Returns:
            ModificationObject if successful
        """
        review = Review(text=review_text, has_modification=True)
        recipe = Recipe(
            recipe_id=recipe_data.get("recipe_id", "test"),
            title=recipe_data.get("title", "Test Recipe"),
            ingredients=recipe_data.get("ingredients", []),
            instructions=recipe_data.get("instructions", []),
        )

        return self.extract_modification(review, recipe)
