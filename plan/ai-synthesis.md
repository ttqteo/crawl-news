# Plan: Optimized AI Synthesis (Local Clustering + LLM)

This plan outlines a zero-cost clustering method and highly efficient LLM summaries.

## 1. Local Clustering (`scripts/cluster_news.py`)

- **Objective**: Use free local resources to group identical stories.
- **Provider**: `scikit-learn` (TF-IDF + Cosine Similarity).
- **Process**:
  1. Read JSON file for the current day.
  2. Convert titles to vectors and calculate similarity.
  3. Group articles with score > 0.75.
  4. Save enriched JSON with `cluster_id` and `sources[]`.

## 2. LLM Summarization (`scripts/daily_digest.py`)

- **Objective**: Generate a single daily "Catch-up" message.
- **Provider**: OpenRouter (using free/cheap models like `xiaomi/mimo-v2-flash:free`).
- **Optimization**: Send all headlines of major clusters in ONE prompt to save tokens.
- **Input**: Top 5-10 clusters from today.
- **Output**: `docs/news/digest.json` (stores only the last few days).

## 3. GitHub Actions Integration

- Add `scikit-learn` and `openai` to `requirements.txt`.
- Update `.github/workflows/crawl.yml` to chain:
  `app.py` -> `cluster_news.py` -> `daily_digest.py` -> `build_index.py`.

## 4. Frontend (docs/index.html)

- Show "Summary of Tomorrow/Yesterday" card at top.
- Cards show source icons instead of just one.
