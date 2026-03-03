## Start Cleaning Stuff Up

First thing I did was make it so I could use UV everywhere (Codex 5.2).

Then I had Sonnet 4.6 w/ Cline look at the code and the requirements doc.

Did a test run and was annoyed the artifacts weren't `.gitignore`d.

---

## Fix: Stale `src/data/` Directory and Fragile Output Path

**Root cause:** `LLMAnalysisPipeline` defaulted `output_dir` to the relative string `"data/enhanced"`. When the pipeline was run from inside the `src/` directory instead of the project root, Python resolved this relative to `src/`, silently creating `src/data/enhanced/` alongside the correct `data/enhanced/`.

**Changes:**

- `src/llm_pipeline/pipeline.py` — default `output_dir` now resolves to an absolute path derived from `__file__` (`<project_root>/data/enhanced`), so it's correct regardless of working directory
- Deleted the stale `src/data/` artifact directory
- `.gitignore` — added `data/enhanced/` and `src/data/` so generated pipeline outputs are never tracked

---

## Magic Strings

We already found one problematic magic string, did a scan, found a couple other minor issues, and went ahead and fixed them. Probably didn't need to do this, but here we are.

---

## "Does the Pipeline Work?" Analysis w/ AI

Now that things are tidy, we can answer the question we've been posed: _"Does the system work?"_

Here's what I'm seeing:

- **We're not processing all the reviews** (just picking a random one), and we're not using the `featured_tweaks` ranking system at all. Probably need to do something like:
  - Build candidate reviews from `featured_tweaks` first, then plain reviews
  - In `pipeline.py`, parse both arrays
  - Deduplicate by normalized text so the same review isn't processed twice
  - Rank candidates with a fixed scoring rule:
    - `is_featured` desc (featured first)
    - `helpful_count` desc (if available; otherwise 0)
    - `rating` desc
    - original index asc (stable tie-breaker)
  - Select top-K deterministically (no randomness)
  - Replace `random.choice` logic in `tweak_extractor.py` with "process first K ranked candidates" — default `top_k_reviews=3`
  - Extract/apply from each selected review; apply valid edits sequentially to the evolving recipe; keep attribution per review in output
  - Add tests to lock behavior: same input run 10 times → same selected reviews and same output; if `featured_tweaks` exists, selected reviews must come from it before plain reviews
  - **Concrete result:** pipeline now picks the right reviews per spec and produces repeatable outputs

- **`modification_type` enum isn't handling compound reviews**

- **The `replace` operation in `RecipeModifier` is silently broken:** fuzzy matching finds the approximate line, but then calls `original_text.replace(edit.find, ...)` — a _literal_ substring search on the original non-fuzzy text. When the LLM's `find` string doesn't exactly appear in the line (common), the replacement silently does nothing. Edit application can report false positives and silently drop edits.
  - _Evidence:_ `recipe_modifier.py` (line 91) uses `original_text.replace(edit.find, ...)` after fuzzy match; if the substring isn't exact, `from_text == to_text` but the change is still recorded. Also, unmatched extracted edits only warn (`recipe_modifier.py` line 121).

- **`EXTRACTION_PROMPT` is malformed**

- **`gpt-3.5-turbo` is old as hell**

- **We need to think about enhancements that don't have any real changes** — like, is that even an enhancement?

- **We're not handling hypothetical language in modifications** — if someone says "next time" that means they didn't actually do it.
  - _Evidence:_ `scraper_v2.py` (line 85) marks phrases like "next time / will make again" as `has_modification=true`
  - _Impact:_ Pipeline applies speculative changes not actually tested
  - _Fix:_ Add explicit `is_hypothetical` filter before extraction, and exclude unless user opts in

- **We should probably think about longer-term testing** if this were a real production-ready system.
  - _Evidence:_ `test_pipeline.py` (line 109) passes "all" mode if at least one recipe succeeds; no assertions for completeness, determinism, or diff validity
  - _Impact:_ False confidence
  - _Fix:_ Add deterministic unit/integration tests with mocked LLM outputs and explicit acceptance thresholds

- **Metadata mapping is broken**
  - _Evidence:_ Scraper stores `preptime`/`cooktime`/`totaltime` (`scraper_v2.py` line 192); `Recipe` model lacks those fields (`models.py` line 125); generator expects `prep_time`/`cook_time`/`total_time` (`enhanced_recipe_generator.py` line 158)
  - _Impact:_ Enhanced output drops timing metadata
  - _Fix:_ Normalize and map timing fields during parse

---

## Plan of Attack

Four things to get this production-ready:

1. Fix review processing (the `random.choice` stuff, `featured_tweaks` stuff)
2. Compound reviews
3. Fuzzy matching in `RecipeModifier`
4. Hypothetical language modifications
5. Small bugfixes (e.g. malformed extraction prompt, metadata mapping)

**Nice to haves:**

- More deterministic tests
- Null enhancements
- Model evals (beyond just updating to GPT-5)
- Batch processing of `extract_top_k_modifications`

---

First PR was for fixing the `random.choice` stuff. While I'm in there, I'm taking the time to add structured output support because it's definitely worth it. Going with `gpt-4.1-mini`.

Cline broke, so fixing that. Looks like they updated their remote MCP stuff.

Shipped updates to the modification type and added a library for fuzzy strings. It doesn't work exactly how I want it to — IMO this would be handled in some other layer/system — so ignoring for now and moving on.

Starting work on QA stuff. I'm going to have a CSV for the video so I'm adding that.

---

## Longer-Term Refactoring Notes

We're doing a lot of small LLM calls without a ton of context. We should probably do a few bigger LLM calls that take all the various changes into account.

Fuzzy searching is still a problem - IMO solved by either using more model calls/tokens.
