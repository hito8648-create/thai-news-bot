# -*- coding: utf-8 -*-
import sys
import os
import json
import feedparser
import google.generativeai as genai
import requests
from dotenv import load_dotenv
from datetime import datetime

# Windows対応 (UTF-8強制)
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

# 設定
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
THREADS_USER_ID = os.getenv("THREADS_USER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HISTORY_FILE = "posted_history.json"

# API初期化
genai.configure(api_key=GEMINI_API_KEY)
# 最多の無料枠を持つ「ライト版」を指定
model = genai.GenerativeModel('gemini-flash-lite-latest')

# ニュースソース (4つ)
SOURCES = [
    {"name": "Bangkok Post", "url": "https://www.bangkokpost.com/rss/data/topstories.xml"},
    {"name": "The Pattaya News", "url": "https://thepattayanews.com/feed/"},
    {"name": "Pattaya Mail", "url": "https://www.pattayamall.com/feed"},
    {"name": "Khaosod English", "url": "https://www.khaosodenglish.com/feed/"}
]

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(link):
    history = load_history()
    history.insert(0, link)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[:50], f, ensure_ascii=False, indent=2)

def fetch_all_headlines():
    all_articles = []
    history = load_history()
    for source in SOURCES:
        print(f"取得中: {source['name']}...", flush=True)
        feed = feedparser.parse(source['url'])
        count = 0
        # 各サイトからの取得を 3件 → 2件に絞ってトークンを節約
        for entry in feed.entries:
            if count >= 2: break
            if entry.link in history: continue
            all_articles.append({
                "source": source["name"],
                "title": entry.title,
                "link": entry.link,
                "description": entry.description if hasattr(entry, 'description') else ""
            })
            count += 1
    return all_articles

def select_and_summarize(articles):
    if not articles: return None, None
    list_str = ""
    for i, a in enumerate(articles):
        list_str += f"[{i}] {a['source']}: {a['title']}\n"

    prompt = f"""
あなたはタイ情認に精通した日本語プロ編集者です。
ニュース見出しから、日本人読者が最も関心を持つ「最高の一記事」を1件だけ厳選し、投稿文を作成してください。

【ニュースリスト】
{list_str}

【ライティングの絶対ルール】
・「AIらしさ」を徹底的に排除。
・「〜という重要なニュースです」「〜に注目しましょう」といった結びは禁止。
・専門記者が鋭い洞察を込めて書いているかのようなトーン。

[投稿文構成]
1. (ヘッドラインタイトル - 🚨や🇹🇭などの絵文字から開始)
2. (空白行)
3. (事実の要約：核心のみを伝える)
4. (空白行)
5. (本音の洞察/インパクト：実利的な視点)

回答の最後に、必ず「INDEX:[番号]」とだけ書き添えてください。
"""
    response = model.generate_content(prompt)
    output_text = response.text.strip()
    try:
        if "INDEX:" in output_text:
            parts = output_text.split("INDEX:")
            post_content = parts[0].strip()
            idx_cleaned = "".join(filter(str.isdigit, parts[1]))
            idx = int(idx_cleaned) if idx_cleaned else 0
        else:
            post_content = output_text
            idx = 0
        selected_article = articles[idx] if idx < len(articles) else articles[0]
        post_content += f"\n\n{selected_article['link']}"
    except:
        post_content = output_text
        selected_article = articles[0]
    return post_content, selected_article

def get_threads_user_id():
    url = f"https://graph.threads.net/v1.0/me?fields=id&access_token={THREADS_ACCESS_TOKEN}"
    res = requests.get(url)
    return res.json().get('id') if res.status_code == 200 else None

def post_to_threads(text):
    global THREADS_USER_ID
    if not THREADS_USER_ID:
        THREADS_USER_ID = get_threads_user_id()
    
    res_c = requests.post(f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads", data={
        "media_type": "TEXT", "text": text, "access_token": THREADS_ACCESS_TOKEN
    })
    if res_c.status_code != 200:
        print(f"コンテナ作成失敗: {res_c.text}")
        return False
    
    creation_id = res_c.json().get('id')
    res_p = requests.post(f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish", data={
        "creation_id": creation_id, "access_token": THREADS_ACCESS_TOKEN
    })
    return res_p.status_code == 200

def main():
    print(f"--- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 定期実行開始 ---", flush=True)
    articles = fetch_all_headlines()
    if not articles:
        print("新規記事なし。")
        return
        
    print(f"{len(articles)}件からAI記者が厳選中...", flush=True)
    post_content, selected_article = select_and_summarize(articles)
    if not post_content: return
    
    print("\n【決定した投稿案】\n" + post_content + "\n", flush=True)
    
    if post_to_threads(post_content):
        print("Threadsへの投稿に成功しました！ 🎉", flush=True)
        save_history(selected_article['link'])
    else:
        print("【失敗】投稿できませんでした。", flush=True)

if __name__ == "__main__":
    main()
