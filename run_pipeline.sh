#!/bin/bash
# High-level pipeline to run the full news cycle
echo "--- 1. Crawling news ---"
python app.py

echo "--- 2. AI Clustering ---"
python scripts/cluster_news.py

echo "--- 3. AI daily digest ---"
python scripts/daily_digest.py

echo "--- 4. Building index ---"
python scripts/build_index.py

echo "--- Pipeline completed! ---"
