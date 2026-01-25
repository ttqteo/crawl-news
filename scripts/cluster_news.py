#!/usr/bin/env python3
import os, json, glob
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from openai import OpenAI

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")

def get_ai_summary(master_title, cluster_items, client):
    """Generate a synthesized summary for a cluster of news using LLM."""
    if not client: return None
    
    # Bundle all content into a prompt
    context = []
    for it in cluster_items:
        context.append(f"Title: {it['title']}\nSummary: {it['summary']}")
    
    prompt = f"""Bạn là một chuyên gia tin tức. Hãy viết một bản tóm tắt tổng hợp (synthesized summary) duy nhất cho nhóm tin tức cùng chủ đề dưới đây.
Tiêu đề chính: {master_title}

Dữ liệu từ các nguồn:
{"---".join(context)}

Yêu cầu:
1. Viết bằng tiếng Việt, súc tích (khoảng 3-4 câu).
2. Tập trung vào sự kiện chính và các con số/chi tiết quan trọng nhất từ tất cả nguồn.
3. Không lặp lại tên báo trong nội dung tóm tắt.
4. Văn phong báo chí hiện đại.
"""

    try:
        response = client.chat.completions.create(
            model="xiaomi/mimo-v2-flash:free",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"  AI Summary Error: {e}")
        return None

def cluster_news(news_dir="docs/news", threshold=0.75):
    files = glob.glob(os.path.join(news_dir, "*.json"))
    files = [f for f in files if "index.json" not in f and "digest" not in f]
    
    # Initialize OpenAI client for OpenRouter
    api_key = os.environ.get("OPENROUTER_API_KEY")
    client = None
    if api_key:
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    else:
        print("Warning: OPENROUTER_API_KEY not found. Skipping AI cluster summarization.")

    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        items = list(data.values())
        if not items: continue
        
        # Prepare titles for TF-IDF
        titles = [it.get("title", "") for it in items]
        if len(titles) < 2: 
            # Still save but identify as single source
            for it in items: it["cluster_count"] = 1
        else:
            vectorizer = TfidfVectorizer(stop_words=None)
            tfidf_matrix = vectorizer.fit_transform(titles)
            sim_matrix = cosine_similarity(tfidf_matrix)
            
            assigned = [False] * len(items)
            clusters = []
            
            for idx in range(len(items)):
                if assigned[idx]: continue
                current_cluster = [idx]
                assigned[idx] = True
                for other_idx in range(idx + 1, len(items)):
                    if not assigned[other_idx] and sim_matrix[idx][other_idx] > threshold:
                        current_cluster.append(other_idx)
                        assigned[other_idx] = True
                clusters.append(current_cluster)
                
            final_items = {}
            for c in clusters:
                master_idx = c[0]
                master = items[master_idx]
                
                sources = []
                cluster_items_data = [] # To send to LLM
                for idx in c:
                    it = items[idx]
                    sources.append({"name": it["source"], "link": it["link"]})
                    cluster_items_data.append(it)
                
                master["sources"] = sources
                master["cluster_count"] = len(sources)
                
                # If hot story (multiple sources), call AI
                if len(sources) > 1 and client:
                    print(f"  Synthesizing cluster: {master['title'][:50]}... ({len(sources)} sources)")
                    master["ai_summary"] = get_ai_summary(master["title"], cluster_items_data, client)
                
                final_items[master["item_id"]] = master
            items = list(final_items.values())
            
        # Sort and Save back
        items.sort(key=lambda x: x.get("published", ""), reverse=True)
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump({it["item_id"]: it for it in items}, f, ensure_ascii=False, separators=(",", ":"))
            
    print(f"Clustered {len(files)} files.")

if __name__ == "__main__":
    cluster_news()
