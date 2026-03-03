# Refactor Proposal: Fewer, Bigger LLM Calls

## Goal
Reduce per-recipe call count and improve consistency by moving from many small independent extraction calls to a small number of structured planning calls.

Current pattern (roughly):

1. Rank reviews
2. Call LLM once per selected review (top-K)
3. Apply each modification sequentially

With `top_k_reviews=3`, this is 3 extraction calls per recipe, and each call lacks full awareness of the other selected reviews.

## Why Refactor

1. **Cross-review conflicts** are not resolved before application.
2. **Inconsistent style/units** across independent calls (for example `1/2 cup` vs `0.5 cup`).
3. **Higher cost/latency** from multiple calls.
4. **No global reasoning** about hypothetical vs concrete phrasing across all chosen reviews.

## Target Architecture (Two Calls Per Recipe)

### Call A: Multi-review extraction and normalization
Input:

- Original recipe
- Top-K ranked reviews (full text + metadata)

Output (structured):

- Parsed candidate edits grouped by review
- Flags per candidate: `is_concrete`, `is_hypothetical`, `confidence`
- Normalized quantities/units (canonical form)

### Call B: Global merge and conflict resolution
Input:

- Original recipe
- All candidate edits from Call A

Output (structured final plan):

- `final_edits`: one conflict-resolved edit set
- `discarded_edits`: with reason (`hypothetical`, `conflict_loser`, `low_confidence`, `duplicate`)
- `attribution_map`: final edit -> source review(s)

Then apply only `final_edits` once.

## Optional Variant (Single Call)
One large call can do extract + resolve in a single pass. This is simplest operationally but harder to debug. Two-call design is usually a better tradeoff for observability.

## Data Contract Changes

Add/extend internal schema to support:

1. Candidate edit metadata:
   - `source_review_id`
   - `is_concrete`
   - `confidence`
2. Final plan metadata:
   - `resolved_from` (list of candidate IDs)
   - `discard_reason`

These can remain internal and not change external enhanced recipe format initially.

## Migration Plan

1. **Phase 1**: Introduce new planner path behind a feature flag:
   - `MERGED_PLANNER_ENABLED=true/false`
2. **Phase 2**: Run both old and new in shadow mode on the same recipes.
3. **Phase 3**: Compare metrics and promote new planner if improved.

## Evaluation Metrics

Track before/after:

1. Malformed replacement rate (for example malformed numeric strings).
2. `MODIFICATION_NO_CHANGES` rate.
3. Contradictory edit rate on same target line.
4. Tokens per recipe and wall-clock latency.
5. Human review score on output coherence.

## Expected Benefits

1. Fewer malformed merged strings.
2. Better handling of hypothetical language.
3. More consistent quantity formatting.
4. Lower API overhead for larger datasets.

## Risks

1. Bigger prompts can increase per-call token usage.
2. Single-plan failure can affect whole recipe output.
3. Requires stronger schema validation and fallback paths.

Mitigations:

1. Keep strict structured outputs.
2. Add fallback to old per-review extraction when parse fails.
3. Preserve verbose logs of discarded/merged decisions.

## Suggested Next Implementation Step
Implement **Call A only** first (multi-review extraction with concrete/hypothetical flag), keep existing apply logic, and measure improvement before introducing global merge.
