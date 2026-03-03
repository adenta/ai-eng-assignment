## Fix start cleaning stuff up (Written by andrew)

The first thing I did was make it so I could use UV everywhere (Codex 5.2)

Then I had sonnet 4.6 w/ cline look at the code and the doc of the requirement.

I did a test run and was annoyed the artifacts weren't .gitignored

## Fix: stale `src/data/` directory and fragile output path

**Root cause:** `LLMAnalysisPipeline` defaulted `output_dir` to the relative string `"data/enhanced"`. When the pipeline was run from inside the `src/` directory instead of the project root, Python resolved this relative to `src/`, silently creating `src/data/enhanced/` alongside the correct `data/enhanced/`.

**Changes:**

- `src/llm_pipeline/pipeline.py` — default `output_dir` now resolves to an absolute path derived from `__file__` (`<project_root>/data/enhanced`), so it's correct regardless of working directory
- Deleted the stale `src/data/` artifact directory
- `.gitignore` — added `data/enhanced/` and `src/data/` so generated pipeline outputs are never tracked

## magic strings (Written by andrew)

so we already found one probelmatic magic string, did a scan and found a couple other minor problems,went ahead and fixed them. probably didnt need to do this.

## "Does the pipeline work" analysis w/ AI

now that things are tidy, we can answer the question we have been proposed: "Does the system work"

What I'm seeing:

- we are not processing all the reviews (just picking a random one.)
  - we are also not using featured_tweaks ranking system at all
    probably need to do something like
    Solution is: make review selection a deterministic ranking step before LLM extraction.

Build candidate reviews from featured_tweaks first, then reviews
In pipeline.py, parse both arrays.
Deduplicate by normalized text so same review isn’t processed twice.
Rank candidates with a fixed scoring rule
is_featured desc (featured first)
helpful_count desc (if available; otherwise 0)
rating desc
original index asc (stable tie-breaker)
Select top-K deterministically (no randomness)
Replace random.choice logic in tweak_extractor.py with “process first K ranked candidates”.
Default top_k_reviews=3.
Extract/apply from each selected review
Run extractor per selected review.
Apply valid edits sequentially to the evolving recipe.
Keep attribution per review in output.
Add tests to lock behavior
Same input run 10 times => same selected reviews and same output.
If featured_tweaks exists, selected reviews must come from it before plain reviews.
Concrete result: pipeline now picks the right reviews per spec and produces repeatable outputs.

- modification_type enum isn't handing compound reviews
- **\*The `replace` operation in `RecipeModifier` is silently broken**: fuzzy matching finds the approximate line, but then calls `original_text.replace(edit.find, ...)` — a _literal_ substring search on the original non-fuzzy text. When the LLM's `find` string doesn't exactly appear in the line (common), the replacement silently does nothing.\*
  Edit application can report false positives and silently drop edits
  Evidence: recipe_modifier.py (line 91) uses original_text.replace(edit.find, ...) after fuzzy match; if substring isn’t exact, from_text == to_text but change is still recorded. Also unmatched extracted edits only warn (recipe_modifier.py (line 121)).

- EXTRACTION_PROMPT is malformed
- gpt-3.5-turbo is old af
- we need to think about an enhancement that doesn't have any real changes. like, is that even an enhancement?
- we are not handling hypothetical language modifications (if someone says next time that means they didnt actually do it)
  Hypothetical language is treated as applied modification
  Evidence: scraper_v2.py (line 85) marks phrases like “next time / will make again” as has_modification=true.
  Impact: Pipeline applies speculative changes not actually tested.
  Fix: Add explicit is_hypothetical filter before extraction, and exclude unless user opts in.
- we should probably think about longer term testing if this were a real, production ready system
  Validation/testing is insufficient for correctness claims
  Evidence: test_pipeline.py (line 109) passes “all” mode if at least one recipe succeeds; no assertions for completeness, determinism, or diff validity.
  Impact: False confidence.
  Fix: Add deterministic unit/integration tests with mocked LLM outputs and explicit acceptance thresholds.

- metadata mapping is broken
  Metadata mapping is broken
  Evidence: scraper stores preptime/cooktime/totaltime (scraper_v2.py (line 192)); Recipe model lacks those fields (models.py (line 125)); generator expects prep_time/cook_time/total_time (enhanced_recipe_generator.py (line 158)).
  Impact: Enhanced output drops timing metadata.
  Fix: Normalize and map timing fields during parse.

# Plan of attack

Four things to get this production ready

1. fix review processing system (random.choice stuff, featured tweaks stuff)
2. compound reviews
3. fuzzy matching in RecipeModifer
4. hypothetical language modifications
5. small bugfixes (eg: malformed extraction prompt, metadata mapping)

nice to haves:

- we really need more deterministic tests
- null enhancements
- model evals (beyond just updating to a gpt5)
- batch processing of extract_top_k_modifications

First PR was for fixing the random choice stuff. while Im here, im taking the time to add structured output support because its def worth the time. Going with gpt 4.1 mini.

Cline broke, so fixing that. Looks like they updated their remote MCP stuff

I shipped updates to the modification type and added a library for fuzzy strings. It doesn't work exactly how i want it to, IMO this would be done in some other layer/system, ignoring for now and moving on.

starting work on QA stuff. I am going to have a CSV for the video so i am adding that.

Longer term refactoring:
we are doing a lot of small LLM calls without a ton of context, we should probably do a few bigger llm calls that take all of the various changes into account

didnt fix fuzzy searching

didnt fix hypothetical modifications
