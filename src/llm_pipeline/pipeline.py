"""
LLM Analysis Pipeline - Main Orchestrator

This module coordinates the complete 3-step pipeline:
1. Extract modifications from reviews
2. Apply modifications to recipes
3. Generate enhanced recipes with attribution

Processes recipe data from scraped JSON files and outputs enhanced recipes.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# Absolute path to the project root (two levels up from this file: src/llm_pipeline/ -> src/ -> root)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_OUTPUT_DIR = str(_PROJECT_ROOT / "data" / "enhanced")

from dotenv import load_dotenv
from loguru import logger

from .enhanced_recipe_generator import EnhancedRecipeGenerator
from .models import EnhancedRecipe, Recipe, Review
from .recipe_modifier import RecipeModifier
from .tweak_extractor import TweakExtractor


class LLMAnalysisPipeline:
    """Complete pipeline for analyzing recipes and generating enhanced versions."""

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        output_dir: str = _DEFAULT_OUTPUT_DIR,
        pipeline_version: str = "1.0.0",
        top_k_reviews: int = 3,
    ):
        """
        Initialize the complete LLM Analysis Pipeline.

        Args:
            openai_api_key: OpenAI API key (loads from env if not provided)
            output_dir: Directory to save enhanced recipes
            pipeline_version: Version identifier for tracking
            top_k_reviews: Maximum number of ranked reviews to extract and apply.
                           Featured reviews are always prioritised first.
                           Set to a very large number (e.g. 999) to process all
                           reviews deterministically.
        """
        # Load environment variables
        load_dotenv()

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.top_k_reviews = top_k_reviews

        # Initialize pipeline components
        self.tweak_extractor = TweakExtractor(api_key=openai_api_key)
        self.recipe_modifier = RecipeModifier()
        self.enhanced_generator = EnhancedRecipeGenerator(
            pipeline_version=pipeline_version
        )

        logger.info(f"Initialized LLM Analysis Pipeline v{pipeline_version}")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Top-K reviews per recipe: {self.top_k_reviews}")

    def load_recipe_data(self, file_path: str) -> Dict[str, Any]:
        """
        Load recipe data from JSON file.

        Args:
            file_path: Path to recipe JSON file

        Returns:
            Recipe data dictionary
        """
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def parse_recipe_data(self, recipe_data: Dict[str, Any]) -> Recipe:
        """
        Parse raw recipe data into Recipe object.

        Args:
            recipe_data: Raw recipe data from JSON

        Returns:
            Recipe object
        """
        return Recipe(
            recipe_id=recipe_data.get("recipe_id", "unknown"),
            title=recipe_data.get("title", "Unknown Recipe"),
            ingredients=recipe_data.get("ingredients", []),
            instructions=recipe_data.get("instructions", []),
            description=recipe_data.get("description"),
            servings=recipe_data.get("servings"),
            rating=recipe_data.get("rating"),
        )

    def parse_reviews_data(self, recipe_data: Dict[str, Any]) -> List[Review]:
        """
        Parse raw review data into Review objects.

        Reads both ``featured_tweaks`` and ``reviews`` arrays, deduplicates by
        normalised text (whitespace-collapsed, lower-cased), and preserves the
        ``is_featured`` flag so the downstream ranker can prioritise featured
        reviews correctly.

        Args:
            recipe_data: Raw recipe data containing reviews

        Returns:
            Deduplicated list of Review objects (featured entries kept over
            plain duplicates)
        """
        seen_keys: dict[str, Review] = {}

        def _normalise(text: str) -> str:
            """Collapse whitespace and lower-case for dedup comparison."""
            return " ".join(text.lower().split())

        def _add(review_data: Dict[str, Any], is_featured: bool) -> None:
            text = review_data.get("text", "").strip()
            if not text:
                return
            key = _normalise(text)
            if key not in seen_keys:
                seen_keys[key] = Review(
                    text=text,
                    rating=review_data.get("rating"),
                    username=review_data.get("username"),
                    has_modification=review_data.get("has_modification", False),
                    is_featured=is_featured,
                    helpful_count=review_data.get("helpful_count", 0),
                    date=review_data.get("date"),
                )
            else:
                # If we've now seen a featured version, upgrade the existing entry.
                if is_featured and not seen_keys[key].is_featured:
                    seen_keys[key] = seen_keys[key].model_copy(
                        update={"is_featured": True}
                    )

        # Featured tweaks first so they win any dedup collision by default.
        for review_data in recipe_data.get("featured_tweaks", []):
            _add(review_data, is_featured=True)

        for review_data in recipe_data.get("reviews", []):
            _add(review_data, is_featured=False)

        return list(seen_keys.values())

    def process_single_recipe(
        self, recipe_file: str, save_output: bool = True
    ) -> Optional[EnhancedRecipe]:
        """
        Process a single recipe through the complete pipeline.

        Reviews are ranked deterministically (featured first, then by helpful
        count and rating) and the top ``self.top_k_reviews`` are extracted and
        applied in order.  No random selection is used.

        Args:
            recipe_file: Path to recipe JSON file
            save_output: Whether to save the enhanced recipe

        Returns:
            EnhancedRecipe if successful, None otherwise
        """
        try:
            logger.info(f"Processing recipe file: {recipe_file}")

            # Step 0: Load and parse data
            recipe_data = self.load_recipe_data(recipe_file)
            recipe = self.parse_recipe_data(recipe_data)
            reviews = self.parse_reviews_data(recipe_data)

            featured_count = sum(1 for r in reviews if r.is_featured)
            mod_count = sum(1 for r in reviews if r.has_modification)
            logger.info(f"Loaded recipe: {recipe.title}")
            logger.info(
                f"Found {len(reviews)} unique reviews "
                f"({featured_count} featured, {mod_count} with modifications)"
            )

            if not any(r.has_modification for r in reviews):
                logger.warning("No reviews with modifications found")
                return None

            # Step 1: Extract modifications from top-K ranked reviews
            logger.info(
                f"Step 1: Extracting modifications from top-{self.top_k_reviews} ranked reviews..."
            )
            extraction_results = self.tweak_extractor.extract_top_k_modifications(
                reviews, recipe, top_k=self.top_k_reviews
            )

            if not extraction_results:
                logger.warning("No modifications could be extracted")
                return None

            logger.info(
                f"Successfully extracted {len(extraction_results)} modification(s)"
            )

            # Step 2: Apply modifications sequentially to the evolving recipe
            logger.info("Step 2: Applying modifications to recipe...")
            current_recipe = recipe
            applied_modifications = []

            for i, (modification, source_review) in enumerate(extraction_results, start=1):
                logger.info(
                    f"  Applying modification {i}/{len(extraction_results)}: "
                    f"{modification.modification_type}"
                )
                current_recipe, change_records = self.recipe_modifier.apply_modification(
                    current_recipe, modification
                )
                applied_modifications.append(
                    {
                        "modification": modification,
                        "source_review": source_review,
                        "change_records": change_records,
                    }
                )
                logger.info(f"    → {len(change_records)} change(s) applied")

            total_changes = sum(
                len(entry["change_records"]) for entry in applied_modifications
            )
            logger.info(
                f"All modifications applied: {total_changes} total change(s) across "
                f"{len(applied_modifications)} modification(s)"
            )

            # Step 3: Generate enhanced recipe with attribution
            logger.info("Step 3: Generating enhanced recipe with attribution...")
            enhanced_recipe = self.enhanced_generator.generate_enhanced_recipe(
                recipe, current_recipe, applied_modifications
            )

            logger.info(f"Generated enhanced recipe: {enhanced_recipe.title}")

            # Save output
            if save_output:
                output_filename = (
                    f"enhanced_{recipe.recipe_id}_"
                    f"{recipe.title.lower().replace(' ', '-')[:30]}.json"
                )
                output_path = self.output_dir / output_filename
                self.enhanced_generator.save_enhanced_recipe(
                    enhanced_recipe, str(output_path)
                )

            return enhanced_recipe

        except Exception as e:
            logger.error(f"Failed to process recipe {recipe_file}: {e}")
            import traceback

            traceback.print_exc()
            return None

    def process_recipe_directory(
        self, data_dir: str = str(_PROJECT_ROOT / "data")
    ) -> List[EnhancedRecipe]:
        """
        Process all recipe files in a directory.

        Args:
            data_dir: Directory containing recipe JSON files

        Returns:
            List of successfully processed EnhancedRecipe objects
        """
        data_path = Path(data_dir)
        recipe_files = list(data_path.glob("recipe_*.json"))

        logger.info(f"Found {len(recipe_files)} recipe files to process")

        enhanced_recipes = []
        for recipe_file in recipe_files:
            logger.info(f"\n{'=' * 60}")
            enhanced_recipe = self.process_single_recipe(str(recipe_file))

            if enhanced_recipe:
                enhanced_recipes.append(enhanced_recipe)
                logger.info(f"✓ Successfully processed: {enhanced_recipe.title}")
            else:
                logger.warning(f"✗ Failed to process: {recipe_file.name}")

        logger.info(f"\n{'=' * 60}")
        logger.info(
            f"Pipeline complete: {len(enhanced_recipes)}/{len(recipe_files)} recipes successfully enhanced"
        )

        return enhanced_recipes

    def generate_summary_report(
        self, enhanced_recipes: List[EnhancedRecipe]
    ) -> Dict[str, Any]:
        """
        Generate a summary report of pipeline results.

        Args:
            enhanced_recipes: List of enhanced recipes

        Returns:
            Summary report dictionary
        """
        if not enhanced_recipes:
            return {"status": "no_recipes_processed"}

        total_modifications = sum(
            len(recipe.modifications_applied) for recipe in enhanced_recipes
        )
        total_changes = sum(
            recipe.enhancement_summary.total_changes for recipe in enhanced_recipes
        )

        change_type_counts = {}
        for recipe in enhanced_recipes:
            for change_type in recipe.enhancement_summary.change_types:
                change_type_counts[change_type] = (
                    change_type_counts.get(change_type, 0) + 1
                )

        report = {
            "pipeline_summary": {
                "recipes_processed": len(enhanced_recipes),
                "total_modifications_applied": total_modifications,
                "total_changes_made": total_changes,
                "change_type_distribution": change_type_counts,
            },
            "enhanced_recipes": [
                {
                    "recipe_id": recipe.recipe_id,
                    "title": recipe.title,
                    "modifications_count": len(recipe.modifications_applied),
                    "changes_count": recipe.enhancement_summary.total_changes,
                    "change_types": recipe.enhancement_summary.change_types,
                }
                for recipe in enhanced_recipes
            ],
        }

        return report

    def save_summary_report(
        self, enhanced_recipes: List[EnhancedRecipe], output_path: Optional[str] = None
    ) -> str:
        """
        Save pipeline summary report to JSON file.

        Args:
            enhanced_recipes: List of enhanced recipes
            output_path: Path to save report (auto-generated if None)

        Returns:
            Path to saved report
        """
        if output_path is None:
            output_path = str(self.output_dir / "pipeline_summary_report.json")

        report = self.generate_summary_report(enhanced_recipes)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved pipeline summary report to: {output_path}")
        return output_path
