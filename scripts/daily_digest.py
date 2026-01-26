import datetime
import os
import json
import re

from openai import OpenAI

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")

def generate_digest(news_dir="docs/news"):
    # Get today's and yesterday's files in Vietnam Time
    now = datetime.datetime.now(TIMEZONE)
    today = now.strftime("%m-%d-%Y")
    yesterday = (now - datetime.timedelta(days=1)).strftime("%m-%d-%Y")
    
    selected_files = []
    for d in [today, yesterday]:
        p = os.path.join(news_dir, f"{d}.json")
        if os.path.exists(p): selected_files.append(p)
        
    if not selected_files: return
    
    # Collect top items
    all_headlines = []
    for fpath in selected_files:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            items = list(data.values())
            items.sort(key=lambda x: x.get("cluster_count", 0), reverse=True)
            for it in items[:15]:
                all_headlines.append({
                    "title": it['title'],
                    "source": it['source'],
                    "link": it['link']
                })
                
    if not all_headlines: return
    
    # Format headlines text with links for prompt
    headlines_text = "\n".join([f"- {h['title']} (Nguồn: {h['source']}, Link: {h['link']})" for h in all_headlines])

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("No OPENROUTER_API_KEY found. Skipping digest.")
        return
        
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    
    # Vietnamese display date for prompt
    display_date = now.strftime("%d/%m/%Y")

    prompt = f"""Bạn là một biên tập viên tin tức AI chuyên nghiệp. Hôm nay là ngày {display_date}. 
Hãy phân tích các tin tức sau và tạo một bản tin "Catch up" (Dòng thời gian sự kiện) dưới định dạng JSON.

Yêu cầu nội dung:
1. "summary": Một câu tóm tắt cực ngắn (khoảng 20 từ) bao quát toàn bộ ngày {display_date}.
2. "timeline": Một danh sách gồm 4-6 sự kiện quan trọng nhất của ngày hôm nay ({display_date}). Mỗi sự kiện có:
   - "time": Mốc thời gian hoặc thứ tự (VD: "Sáng nay", "10:00", "Tiêu điểm").
   - "title": Tiêu đề ngắn gọn của sự kiện.
   - "content": Nội dung chi tiết sự kiện (1-2 câu). MUST include key facts.
   - "sources": Một danh sách các đối tượng nguồn tin {{"name": "Tên báo", "link": "đường dẫn"}}.

Yêu cầu kỹ thuật:
- Ngôn ngữ: Tiếng Việt.
- Sử dụng chính xác đường dẫn (Link) từ dữ liệu đầu vào làm nguồn trích dẫn.
- Tuyệt đối không tự bịa ra ngày tháng khác ngày {display_date}.
- Trả về DUY NHẤT định dạng JSON.

Danh sách tin tức thô:
{headlines_text}

Trả về JSON schema:
{{
  "summary": "...",
  "timeline": [
    {{
      "time": "...", 
      "title": "...", 
      "content": "...",
      "sources": [{{"name": "Tên báo", "link": "..."}}]
    }}
  ]
}}
"""

    try:
        response = client.chat.completions.create(
            model="xiaomi/mimo-v2-flash:free", 
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        raw_content = response.choices[0].message.content
        # Clean potential markdown block
        json_str = re.sub(r'```json\s*|\s*```', '', raw_content).strip()
        result = json.loads(json_str)
        
        digest_data = {
            "date": today,
            "summary": result.get("summary", ""),
            "timeline": result.get("timeline", []),
            "updated": now.isoformat()
        }
        
        with open(os.path.join(news_dir, f"digest-{today}.json"), "w", encoding="utf-8") as f:
            json.dump(digest_data, f, ensure_ascii=False, separators=(",", ":"))
        
        # Also save as daily.json (or keep digest.json) for the "Latest" pointer
        with open(os.path.join(news_dir, "digest.json"), "w", encoding="utf-8") as f:
            json.dump(digest_data, f, ensure_ascii=False, separators=(",", ":"))
            
        print(f"Structured daily digest generated: digest-{today}.json and digest.json")
    except Exception as e:
        print(f"Error generating digest: {e}")

if __name__ == "__main__":
    generate_digest()
