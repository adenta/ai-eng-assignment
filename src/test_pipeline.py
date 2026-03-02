#!/usr/bin/env python3
"""
LLM Analysis Pipeline Test Script

This script tests the complete 3-step pipeline with support for both single recipe
testing and full recipe directory validation.

Usage:
    uv run python src/test_pipeline.py single  # Test single recipe
    uv run python src/test_pipeline.py all     # Test all recipes
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from llm_pipeline.pipeline import LLMAnalysisPipeline
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

# Load environment variables from repository .env file regardless of cwd
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


def test_single_recipe():
    """Test the pipeline with the chocolate chip cookie recipe."""

    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set")
        logger.info("Please set your OpenAI API key in .env file")
        return False

    # Initialize pipeline
    try:
        pipeline = LLMAnalysisPipeline(output_dir=str(DATA_DIR / "enhanced"))
        logger.info("Pipeline initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize pipeline: {e}")
        return False

    # Test with chocolate chip cookie recipe
    recipe_file = DATA_DIR / "recipe_10813_best-chocolate-chip-cookies.json"
    if not recipe_file.exists():
        logger.error(f"Recipe file not found: {recipe_file}")
        return False

    logger.info(f"Testing with recipe file: {recipe_file}")

    try:
        # Process the recipe
        enhanced_recipe = pipeline.process_single_recipe(
            recipe_file=str(recipe_file),
            save_output=True
        )

        if enhanced_recipe:
            logger.success("✓ Single recipe test successful!")
            logger.info(f"Enhanced recipe: {enhanced_recipe.title}")
            logger.info(f"Modifications applied: {len(enhanced_recipe.modifications_applied)}")
            logger.info(f"Total changes: {enhanced_recipe.enhancement_summary.total_changes}")
            logger.info(f"Expected impact: {enhanced_recipe.enhancement_summary.expected_impact}")
            return True
        else:
            logger.error("✗ Single recipe test failed - no enhanced recipe generated")
            return False

    except Exception as e:
        logger.error(f"Single recipe test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_all_recipes():
    """Test the pipeline with all scraped recipes."""

    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set")
        logger.info("Please set your OpenAI API key in .env file")
        return False

    # Initialize pipeline
    try:
        pipeline = LLMAnalysisPipeline(output_dir=str(DATA_DIR / "enhanced"))
        logger.info("Pipeline initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize pipeline: {e}")
        return False

    try:
        # Count total recipe files before processing
        total_recipe_files = list(Path(DATA_DIR).glob("recipe_*.json"))
        total_count = len(total_recipe_files)

        # Identify which recipes have reviews with modifications (can be enhanced)
        enhanceable_files = []
        skippable_files = []
        for recipe_file in total_recipe_files:
            import json
            with open(recipe_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            has_mods = any(
                r.get("has_modification", False)
                for r in data.get("featured_tweaks", []) + data.get("reviews", [])
            )
            if has_mods:
                enhanceable_files.append(recipe_file.name)
            else:
                skippable_files.append(recipe_file.name)

        if skippable_files:
            logger.warning(
                f"{len(skippable_files)} recipe(s) have no reviews with modifications "
                f"and cannot be enhanced: {skippable_files}"
            )

        # Process all recipes
        enhanced_recipes = pipeline.process_recipe_directory(
            data_dir=str(DATA_DIR)
        )

        # Generate summary report
        report_path = pipeline.save_summary_report(enhanced_recipes)

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Enhanced recipes: {len(enhanced_recipes)}/{total_count} total")
        logger.info(f"Summary report saved to: {report_path}")

        # Success only if all enhanceable recipes were processed
        if len(enhanced_recipes) == len(enhanceable_files):
            logger.success(
                f"✓ All {len(enhanced_recipes)} enhanceable recipe(s) processed successfully!"
            )
            if skippable_files:
                logger.warning(
                    f"  ({len(skippable_files)} recipe(s) skipped — no reviews with modifications)"
                )
            return True
        else:
            failed_count = len(enhanceable_files) - len(enhanced_recipes)
            logger.error(
                f"✗ {failed_count} enhanceable recipe(s) failed to process "
                f"({len(enhanced_recipes)}/{len(enhanceable_files)} succeeded)"
            )
            return False

    except Exception as e:
        logger.error(f"All recipes test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function with mode selection."""

    # Parse command line argument
    if len(sys.argv) < 2:
        logger.error("Usage: uv run python src/test_pipeline.py [single|all]")
        logger.info("  single - Test single chocolate chip cookie recipe")
        logger.info("  all    - Test all recipes in data directory")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "single":
        logger.info("Starting LLM Analysis Pipeline - Single Recipe Test")
        logger.info("=" * 60)
        success = test_single_recipe()

        logger.info("=" * 60)
        if success:
            logger.success("Single recipe test passed! ✓")
            logger.info("Check the 'data/enhanced/' directory for the enhanced recipe.")
        else:
            logger.error("Single recipe test failed! ✗")
            sys.exit(1)

    elif mode == "all":
        logger.info("Starting LLM Analysis Pipeline - All Recipes Validation")
        logger.info("=" * 60)
        success = test_all_recipes()

        logger.info("=" * 60)
        if success:
            logger.success("All recipes validation passed! ✓")
            logger.info("Check the 'data/enhanced/' directory for all enhanced recipes.")
            logger.info("Check 'data/enhanced/pipeline_summary_report.json' for detailed results.")
        else:
            logger.error("All recipes validation failed! ✗")
            sys.exit(1)

    else:
        logger.error(f"Unknown mode: {mode}")
        logger.error("Usage: uv run python src/test_pipeline.py [single|all]")
        sys.exit(1)


if __name__ == "__main__":
    main()
