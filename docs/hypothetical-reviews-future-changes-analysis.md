# Hypothetical Reviews and Future-Tense Changes

## Purpose
This document explains how the pipeline currently handles reviews that include future or hypothetical language (for example: "next time I will...", "I would...", "I might..."), what improved, and what still fails.

## Why This Matters
The product intent is to apply **community-tested, concrete modifications**.  
Hypothetical statements are not tested modifications and should generally not be applied.

## Current Pipeline Behavior

### 1) Upstream review flagging still admits hypothetical reviews
In scraping, `has_modification` is set using regex rules that include:

- `next time`
- `will make again`
- `definitely make`

Code reference:

- `src/scraper_v2.py` lines 85-90

This means hypothetical reviews can still enter extraction.

### 2) Prompt was tightened to reject hypothetical-only edits
The extraction prompt now includes explicit rules:

- only capture concrete changes actually made
- ignore pure future/hypothetical intent
- return empty edits when nothing concrete exists

Code reference:

- `src/llm_pipeline/prompts.py` lines 33-41

### 3) Latest reports show partial improvement
From `data/enhanced/pipeline_changes_report.csv`:

- Hypothetical-only review converted to no-op:
  - line 26 (`MODIFICATION_NO_CHANGES`, Chicken Parmesan)
  - line 37 (`MODIFICATION_NO_CHANGES`, Sweet Potato Soup)
  - line 44 (`MODIFICATION_NO_CHANGES`, Spicy Apple Cake preference-only)

- Mixed review still applied when it had concrete actions:
  - line 28 (`CHANGE`, Chicken Parmesan)
  - This review contains "next time I will" but also concrete "I added..." content.

## Summary of Results
Current state is **better but not perfect**:

1. Hypothetical-only reviews are now often filtered correctly.
2. Mixed reviews with concrete changes are still applied (usually desired).
3. Some borderline mixed reviews can be over-filtered (concrete parts dropped).

## Practical Interpretation for the Assessment
Suggested wording:

"We improved handling of hypothetical language at extraction time via stricter prompt rules. The pipeline now filters many future-tense-only comments into no-op modifications. However, because hypothetical classification is still prompt-driven and the upstream scraper pre-flags such reviews as mod candidates, behavior is improved but not yet fully deterministic across mixed sentences."

## Recommended Next Step (If Continuing)
If we wanted stronger reliability without a major rewrite:

1. Add a lightweight deterministic pre-filter before extraction:
   - Split review into clauses.
   - Keep clauses with past-tense/applied markers (`I used`, `I added`, `I substituted`).
   - Drop clauses with future-intent markers (`next time`, `I would`, `I might`, `I will`).
2. Pass only retained concrete clauses to the LLM.
3. Keep the stricter prompt as a second safety layer.

This keeps changes scoped while making hypothetical handling more predictable.
