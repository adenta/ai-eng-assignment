# Recipe Enhancement Platform

Automatically enhances recipes by analyzing and applying community-tested modifications from AllRecipes.com. Uses LLM processing to extract meaningful recipe tweaks and apply them with full citation tracking.

## Installation

This project uses [`uv`](https://docs.astral.sh/uv/) for fast, reliable Python package management.

### Prerequisites

- Python 3.13+
- `uv` package manager

## Setup

```bash
# Create .venv (if missing) and install from uv.lock
uv sync
```

No manual activation is required; use `uv run ...` for all commands.

### Environment Variables

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your-openai-api-key-here
```

## Usage

### 1. Scrape Recipes (Optional - data already provided)

```bash
uv run python src/scraper_v2.py
```

### 2. Run Recipe Enhancement Pipeline

```bash
# Test single recipe (chocolate chip cookies)
uv run python src/test_pipeline.py single

# Process all recipes
uv run python src/test_pipeline.py all
```

## Output

### Enhanced Recipes

Enhanced recipes are saved in `data/enhanced/`:

- `enhanced_[recipe_id]_[recipe-name].json` - Individual enhanced recipes with modifications applied
- `pipeline_summary_report.json` - Summary of all processing results

### Data Structure

Original scraped recipes in `data/` directory contain reviews with `has_modification: true` flags. Enhanced recipes include:

```json
{
  "recipe_id": "10813_enhanced",
  "title": "Best Chocolate Chip Cookies (Community Enhanced)",
  "ingredients": ["1 cup butter", "1 additional egg yolk", ...],
  "modifications_applied": [
    {
      "source_review": {
        "text": "I added an extra egg yolk for chewier texture",
        "rating": 5
      },
      "modification_type": ["quantity_adjustment", "addition"],
      "reasoning": "Improves texture and chewiness",
      "changes_made": [...]
    }
  ],
  "enhancement_summary": {
    "total_changes": 1,
    "change_types": ["addition"],
    "expected_impact": "Chewier texture and improved consistency"
  }
}
```

## How It Works

The LLM Analysis Pipeline processes recipes in 3 steps:

1. **Tweak Extraction**: Parses both `featured_tweaks` and `reviews`, deduplicates by normalized text, ranks reviews deterministically (`is_featured` desc, `helpful_count` desc, `rating` desc, stable input order tie-break), and extracts from top-K reviews (`top_k_reviews=3` by default) using OpenAI Structured Outputs with `gpt-4.1-mini-2025-04-14`
2. **Recipe Modification**: Applies changes to the original recipe using fuzzy string matching
3. **Enhanced Recipe Generation**: Creates enhanced version with full citation tracking back to source review

Each run produces one enhanced recipe per original recipe, with complete attribution showing what changed and why.

## Known Limitations

- Conflicting edits across multiple high-ranked reviews can produce awkward merged ingredient text in some outputs.
- Hypothetical/preference language (for example, "next time I will...") can still be treated as an applied modification if it is pre-labeled as `has_modification`.
- Recipe timing metadata (`preptime`, `cooktime`, `totaltime`) from scraped input is not fully mapped into enhanced output fields.
- Current tests focus on key unit behavior and end-to-end smoke validation; broader deterministic regression coverage is still limited.

## Development

```bash
# Add dependencies
uv add <package_name>

# Run tests
uv run python src/test_pipeline.py single
```
