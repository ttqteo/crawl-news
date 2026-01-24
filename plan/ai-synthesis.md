# Plan: AI Synthesis Integration (OpenRouter + GitHub Actions)

This plan outlines the integration of LLM-powered clustering and daily news synthesis into the static news crawler pipeline.

## 1. Backend Enrichment (Python)

We will introduce a new processing step between "Crawl" and "Index".

### A. Thematic Clustering (`scripts/cluster_news.py`)

- **Objective**: Group articles talking about the same event to reduce noise.
- **Provider**: [OpenRouter](https://openrouter.ai/) (e.g., `anthropic/claude-3-haiku` or `google/gemini-pro-1.5`).
- **Logic**:
  1. Read all JSON files for the current/previous day.
  2. Batch article titles/summaries.
  3. Ask LLM to return groups of indices that belong to the same story.
  4. Pick the "best" article as the master and append others as additional sources.
- **Output**: Enriched JSON with a `sources` array for each item.

### B. Daily Digest Generator (`scripts/daily_digest.py`)

- **Objective**: Create a "Catch-up" summary for the previous 24h.
- **Logic**:
  1. Analyze the top 10-15 clusters from yesterday.
  2. Ask LLM to write a 3-5 bullet point "Morning Briefing" in Vietnamese.
- **Output**: `docs/news/digest_YYYY-MM-DD.json`.

## 2. GitHub Actions Update (`.github/workflows/crawl.yml`)

- **Secrets**: Add `OPENROUTER_API_KEY` to GitHub Repo Secrets.
- **Pipeline**:
  1. `Crawl` (Existing)
  2. `pip install openai` (or `requests`)
  3. `python scripts/cluster_news.py`
  4. `python scripts/daily_digest.py`
  5. `Commit & Push` results.

## 3. Frontend Enhancement (`docs/index.html`)

- **Clustered Cards**: Update the UI to show source icons in a stack (e.g., "From VnExpress + 3 others").
- **Immersive Sidebar**: Show links to all original sources for a clustered story.
- **Morning Briefing UI**: Add a premium "AI catch-up" section at the top of the feed that only appears once per day.

## 4. Why OpenRouter?

- **Universal API**: Switch between models (Gemini, Claude, GPT) without changing code.
- **Cost**: haiku/gemini-flash models are extremely cheap for batch processing.

## Next Steps

1. Create the `plan/` folder in the workspace.
2. Initialize `scripts/enrich_utils.py` for API communication.
3. Build the Clustering logic.
