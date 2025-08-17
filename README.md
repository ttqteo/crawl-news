# News RSS Crawler

This repository automatically crawls finance news from configured RSS feeds and saves them as daily JSON files.

Currently supported:
- Vietstock Cổ phiếu
  
Each file contains deduplicated news items for that day.

## Github Page

[https://ttqteo.github.io/crawl-news/](https://ttqteo.github.io/crawl-news/)

## Accessing the data

Since this repo is public, you can fetch the JSON directly from GitHub's raw file service:

[https://raw.githubusercontent.com/ttqteo/crawl-news/master/public/news/08-14-2025.json](https://raw.githubusercontent.com/ttqteo/crawl-news/master/public/news/08-14-2025.json)

## Development

### Prerequisites
- Python 3.9+
- pip (Python package manager)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/ttqteo/crawl-news.git
   cd crawl-news
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the crawler:
   ```bash
   python app.py
   ```

### Project Structure

- `app.py`: Main script for crawling news
- `requirements.txt`: Python dependencies
- `public/news/`: Directory containing the crawled news in JSON format

## Usage

```bash
# Normal mode (skip existing items)
python app.py

# Force update existing items
python app.py --force

# Use a custom config file
python app.py --config my_config.yaml --force
```

---

Copyright to @ttqteo

