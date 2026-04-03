# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import google.generativeai as genai
import requests
import feedparser
from dotenv import load_dotenv
from datetime import datetime

# Windows対応 (UTF-8強制)
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

# 設定
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN_EBI")
THREADS_USER_ID = os.getenv("THREADS_USER_ID_EBI")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY_EBI")
HISTORY_FILE = "posted_history_ebi.json"

# API初期化
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest')

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

def fetch_latest_news():
    print("ニュースを取得中...", flush=True)
    # NHK主要ニュースのRSSを使用
    feed_url = "https://www.nhk.or.jp/rss/news/cat0.xml"
    feed = feedparser.parse(feed_url)
    
    articles = []
    history = load_history()
    count = 0
    for entry in feed.entries:
        if count >= 3: break
        if entry.link in history: continue
        articles.append({
            "title": entry.title,
            "link": entry.link,
            "description": entry.description if hasattr(entry, 'description') else ""
        })
        count += 1
    return articles

def generate_lesson_post(articles):
    if not articles:
        return None, None
        
    # 最新ニュースから1件選んで、そこから単語をレクチャーする
    selected_article = articles[0]
    
    prompt = f"""
あなたは日本人教師「Sensei Ebi (えび先生)」です。
欧米の日本語学び直し層に向けて、Threadsで日本語の短文レッスンを投稿してください。

以下の最新の日本のニュースから【学習者が興味を持ちそうな単語や表現を１つだけ】ピックアップし、そのニュアンスを解説してください。

【ニュースソース】
タイトル: {selected_article['title']}
概要: {selected_article['description']}

[重要：文字数制限]
Threadsの制限のため、必ず「全体で300文字以内（英語150単語程度）」に収めて超・簡潔にしてください。

【投稿構成】
1. タイトル：「今日のニュースから」というニュアンスの英語と絵文字
2. 本文（英語メイン）：選んだ単語と、そのニュアンスを1〜2文で説明。
3. 日本語の例文：(その単語を使った短い日本文を1つ)
4. 応援メッセージ：(短い一言)
5. 固定フレーズ：Don't let your Japanese fade away. Let's restart your journey.

【禁止事項】
・AI特有の回答（問いかけなど）は不要。
・不必要なハッシュタグや、架空のURL、ニュースのURLなどは一切含めないでください。
"""
    
    response = model.generate_content(prompt)
    post_content = response.text.strip()
    
    # 最後にプロフィールへの誘導を追加（URLの直貼りはしない）
    post_content += "\n\nCheck my profile to book a 1-on-1 lesson with me! 🍱✨"
    
    # 【安全装置】500文字を超えていたら、末尾を削る（Threadsの制限対策）
    if len(post_content) > 500:
        post_content = post_content[:497] + "..."
    
    return post_content, selected_article

def post_to_threads(text):
    if not THREADS_USER_ID or not THREADS_ACCESS_TOKEN:
        print("Error: Missing Threads configuration (Token/ID)")
        return False
    
    # 1. コンテナ作成
    url_c = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
    res_c = requests.post(url_c, data={
        "media_type": "TEXT", "text": text, "access_token": THREADS_ACCESS_TOKEN
    })
    
    if res_c.status_code != 200:
        print(f"Container creation failed: {res_c.text}")
        return False
    
    creation_id = res_c.json().get('id')
    
    # 投稿の処理を待つため15秒待機（安全のため残しています）
    print(f"Container ID: {creation_id}. 投稿準備のため15秒待機します...", flush=True)
    time.sleep(15)
    
    # 2. 公開
    url_p = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
    res_p = requests.post(url_p, data={
        "creation_id": creation_id, "access_token": THREADS_ACCESS_TOKEN
    })
    
    if res_p.status_code == 200:
        return True
    else:
        print(f"Publish failed: {res_p.text}")
        return False

def main():
    print(f"--- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (Sensei Ebi Bot) Start ---")
    
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY_EBI is not set.")
        return

    articles = fetch_latest_news()
    if not articles:
        print("新規のニュース記事がありませんでした。")
        return

    print("Generating post content from news...", flush=True)
    post_content, selected_article = generate_lesson_post(articles)
    
    if not post_content:
        return
        
    print(f"Final Content Length: {len(post_content)}")
    print("\n[Generated Post]:")
    print(post_content)
    print("\nPosting to Threads...")
    
    if post_to_threads(post_content):
        print("Success! Posted to Sensei Ebi's Threads.")
        # 重複投稿を避けるため履歴に保存
        save_history(selected_article['link'])
    else:
        print("Failed to post.")

if __name__ == "__main__":
    main()
