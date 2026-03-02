## Fix start cleaning stuff up

The first thing I did was make it so I could use UV everywhere (Codex 5.2)

Then I had sonnet 4.6 w/ cline look at the code and the doc of the requirement.

I did a test run and was annoyed the artifacts weren't .gitignored

## Fix: stale `src/data/` directory and fragile output path

**Root cause:** `LLMAnalysisPipeline` defaulted `output_dir` to the relative string `"data/enhanced"`. When the pipeline was run from inside the `src/` directory instead of the project root, Python resolved this relative to `src/`, silently creating `src/data/enhanced/` alongside the correct `data/enhanced/`.

**Changes:**

- `src/llm_pipeline/pipeline.py` — default `output_dir` now resolves to an absolute path derived from `__file__` (`<project_root>/data/enhanced`), so it's correct regardless of working directory
- Deleted the stale `src/data/` artifact directory
- `.gitignore` — added `data/enhanced/` and `src/data/` so generated pipeline outputs are never tracked
