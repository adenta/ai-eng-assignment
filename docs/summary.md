# Summary of Key Analysis Documents

## 1. Fuzzy Replacement Weirdness

**Problem:** The pipeline produces malformed ingredient strings like `0.1 cup white sugar` and `1.1/2 cup packed brown sugar`.

**Root Cause:** This is a deterministic bug, not random model hallucination. Two things combine to cause it:

1. **Sequential conflicting edits** — Multiple reviews can target the same ingredient line. Each edit is applied one after another, so later edits operate on already-modified text rather than the original.
2. **Fuzzy substring replacement** — `RecipeModifier.apply_edit()` finds the best matching line, then uses fuzzy span matching _within_ that line to find what to replace. When the matched span only covers part of a numeric token, the replacement splices in new text while leaving prefix/suffix characters behind (e.g., `0.` + `1 cup` → `0.1 cup`).

**Why prompt tuning doesn't fully fix it:** Better prompts reduce noisy replacement values, but the substring boundary chosen by the fuzzy replacement logic is entirely in application code — not the LLM.

**Mitigations:** Add numeric token boundary guards, prefer whole-token quantity replacement, merge/conflict-resolve per-ingredient edits before applying, and deduplicate contradictory edits across reviews.

---

## 2. LLM Call Refactor (Fewer, Bigger Calls)

**Problem:** The current pipeline makes one LLM extraction call _per selected review_ (3 calls per recipe with `top_k_reviews=3`). Each call is unaware of the others, leading to cross-review conflicts, inconsistent units, and higher cost/latency.

**Proposed Architecture — Two Calls Per Recipe:**

- **Call A:** Send the original recipe + all top-K reviews together. Get back parsed candidate edits with flags (`is_concrete`, `is_hypothetical`, `confidence`) and normalized quantities.
- **Call B:** Send the original recipe + all candidates from Call A. Get back a conflict-resolved final edit plan with discarded edits and attribution.

Then apply only the final resolved edits once.

**Migration Plan:** Roll out behind a feature flag, run old and new paths in shadow mode, compare metrics, then promote.

**Expected Benefits:** Fewer malformed strings, better hypothetical filtering, consistent quantity formatting, lower API overhead.

**Risks:** Larger prompts, single-point-of-failure per recipe, requires stronger schema validation and fallback paths.

**Recommended first step:** Implement Call A only (multi-review extraction with concrete/hypothetical flag) and measure improvement before adding the global merge step.

---

## 3. Hypothetical Reviews & Future-Tense Changes

**Problem:** Reviews containing future/hypothetical language ("next time I will...", "I would...", "I might...") represent untested ideas, not actual modifications — but the pipeline was applying them anyway.

**What improved:** The extraction prompt was tightened to only capture concrete changes actually made, ignore pure future/hypothetical intent, and return empty edits when nothing concrete exists. This caused several hypothetical-only reviews to correctly become no-ops in the pipeline output.

**What still fails:**

- The upstream scraper still flags hypothetical reviews as modification candidates (via regex matching on phrases like "next time", "will make again"), so they still enter the pipeline.
