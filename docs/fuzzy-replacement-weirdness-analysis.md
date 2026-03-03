# Why Values Like `0.1 cup` and `1.1/2 cup` Happen

## TL;DR
The weird ingredient strings are mainly caused by **sequential edits from multiple reviews** combined with **fuzzy substring replacement** on already-modified lines. Prompt quality affects this, but prompt tuning alone does not fully prevent it.

## Concrete Symptom
In the enhanced cookies output:

- `0.1 cup white sugar`
- `1.1/2 cup packed brown sugar`

See:

- `data/enhanced/enhanced_10813_best-chocolate-chip-cookies.json`

## What Is Happening in the Pipeline

### 1) Multiple conflicting modifications are applied to the same line
`LLMAnalysisPipeline` applies extracted modifications sequentially, mutating the recipe as it goes.

- First review can set sugar to `0.5 cup`.
- Later review can try to set sugar to `1 cup`.
- The second replacement is no longer operating on the original line; it is operating on an already-edited line.

Relevant code path:

- `src/llm_pipeline/pipeline.py` (`process_single_recipe`, sequential application loop)

### 2) Replacement uses fuzzy span matching inside the matched line
`RecipeModifier.apply_edit()`:

1. finds the best candidate line with `find_best_match`
2. then runs `_replace_with_fuzzy_substring` inside that line

`_replace_with_fuzzy_substring` may select a partial span that is "close enough" (threshold-based) and splice in `replace_text`.

Relevant code:

- `src/llm_pipeline/recipe_modifier.py`
  - `find_best_match(...)`
  - `_replace_with_fuzzy_substring(...)`
  - `apply_edit(...)`

### 3) Partial numeric-span replacement can create malformed numbers
If the matched fuzzy span is only part of the quantity token, replacement can leave prefix/suffix characters behind, producing artifacts like:

- `0.1 cup` (leftover `0.` + replaced `1 cup`)
- `1.1/2 cup` (leftover `1.` + replaced `1/2 cup`)

This is why the output looks like a string splice issue.

## Why Prompt Changes Only Partly Help
Prompt constraints can reduce noisy replacement text (for example removing explanatory text in `replace` values), but they do **not** control the final substring boundary chosen by fuzzy replacement logic in `RecipeModifier`.

So prompt improvements are useful, but they do not remove the structural failure mode.

## Key Contributing Factors

1. **Conflicting top-K review edits** on the same ingredient line.
2. **Line-level fuzzy selection + substring-level fuzzy replacement**.
3. **Lack of numeric boundary checks** before replacement.
4. **No conflict-resolution layer** before applying edits.

## How to Explain This in the Assessment
Use this wording:

"The malformed quantity strings are not random model hallucinations alone. They come from deterministic downstream edit application: multiple review-driven edits target the same line, then fuzzy substring replacement can splice inside an already-modified numeric token. Prompt tuning helps reduce noise, but this class of error is fundamentally in edit-application and conflict resolution."

## Potential Mitigations (If We Chose to Fix Later)

1. Add numeric token boundary guards in `replace`.
2. Prefer exact whole-token quantity replacement when numbers are involved.
3. Merge/conflict-resolve per-ingredient edits before applying.
4. Deduplicate or down-rank contradictory edits across reviews.
