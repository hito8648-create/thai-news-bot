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
HISTORY_FILE = "used_words_ebi.json" # 単語の履歴を保存するファイルに変更

# API初期化
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest')

def load_history():
    """過去に使った単語のリストを読み込む"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(word):
    """使った単語を履歴に保存する (最大100件)"""
    history = load_history()
    if word not in history:
        history.insert(0, word)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[:100], f, ensure_ascii=False, indent=2)

def fetch_latest_news():
    print("ニュースを取得中...", flush=True)
    feed_url = "https://www.nhk.or.jp/rss/news/cat0.xml"
    feed = feedparser.parse(feed_url)
    
    articles = []
    count = 0
    # 最新の3件のニュースを候補として取得（同じニュースでも違う単語を探せるようにする）
    for entry in feed.entries:
        if count >= 3: break
        articles.append({
            "title": entry.title,
            "description": entry.description if hasattr(entry, 'description') else ""
        })
        count += 1
    return articles

def generate_lesson_post(articles):
    if not articles:
        return None, None
        
    used_words = load_history()
    used_words_str = ", ".join(used_words) if used_words else "なし"
    
    # 複数のニュース文をくっつけて、AIに単語を探す情報の海として渡す
    source_text = "\n\n".join([f"・{a['title']}\n  {a['description']}" for a in articles])
    
    prompt = f"""
あなたは日本人教師「Sensei Ebi (えび先生)」です。
欧米の日本語学び直し層に向けて、Threadsで日本語の短文レッスンを投稿してください。

以下の日本のテキストから【学習者が興味を持ちそうな単語や表現を１つだけ】ピックアップし、そのニュアンスを解説してください。
★重要ルール★ 以下の単語は過去に解説済みなので【絶対に選ばないでください】: {used_words_str}

【ニュースソース（ここから単語を探す）】
{source_text}

[重要：文字数制限]
Threadsの制限のため、投稿文は必ず「全体で300文字以内（英語150単語程度）」に収めて超・簡潔にしてください。

【出力フォーマット】
必ず以下の2つを順番に出力してください。

1行目: [TARGET_WORD:選んだ単語]
2行目以降: (実際の投稿文)

【投稿構成（2行目以降）】
1. タイトル：「Today's Vocabulary」と絵文字（※Newsという言葉は使わない）
2. 本文（英語メイン）：選んだ単語と、そのニュアンスを1〜2文で説明。
3. 日本語の例文：(その単語を使った短い日本文を1つ)
4. 応援メッセージ：(短い一言)
5. 固定フレーズ：Don't let your Japanese fade away. Let's restart your journey.

【禁止事項】
・投稿文の中にニュースの内容や「ニュースによると」等の言葉は絶対に入れないこと。あくまで「今日の単語」として紹介する。
・不必要なハッシュタグや、架空のURLは含めないでください。
"""
    
    response = model.generate_content(prompt)
    output_text = response.text.strip()
    
    # AIの出力から「ターゲット単語」と「投稿文」を切り分ける
    lines = output_text.split('\n')
    target_word = "Unknown"
    post_lines = []
    
    for line in lines:
        if line.startswith("[TARGET_WORD:"):
            target_word = line.replace("[TARGET_WORD:", "").replace("]", "").strip()
        else:
            post_lines.append(line)
            
    post_content = "\n".join(post_lines).strip()
    
    # 最後にプロフィールへの誘導を追加
    post_content += "\n\nCheck my profile to book a 1-on-1 lesson with me! 🍱✨"
    
    if len(post_content) > 500:
        post_content = post_content[:497] + "..."
    
    return post_content, target_word

def post_to_threads(text):
    if not THREADS_USER_ID or not THREADS_ACCESS_TOKEN:
        print("Error: Missing Threads configuration (Token/ID)")
        return False
    
    url_c = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
    res_c = requests.post(url_c, data={
        "media_type": "TEXT", "text": text, "access_token": THREADS_ACCESS_TOKEN
    })
    
    if res_c.status_code != 200:
        print(f"Container creation failed: {res_c.text}")
        return False
    
    creation_id = res_c.json().get('id')
    
    print(f"Container ID: {creation_id}. 投稿準備のため15秒待機します...", flush=True)
    time.sleep(15)
    
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
        print("ニュース記事が取得できませんでした。")
        return

    print("Generating post content...", flush=True)
    post_content, target_word = generate_lesson_post(articles)
    
    if not post_content:
        return
        
    print(f"Target Word: {target_word}")
    print(f"Final Content Length: {len(post_content)}")
    print("\n[Generated Post]:")
    print(post_content)
    print("\nPosting to Threads...")
    
    if post_to_threads(post_content):
        print("Success! Posted to Sensei Ebi's Threads.")
        # 使った「単語」を履歴に保存して次回以降除外する
        if target_word and target_word != "Unknown":
            save_history(target_word)
    else:
        print("Failed to post.")

if __name__ == "__main__":
    main()
