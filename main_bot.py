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
# 明日からの運用を見据えた「最新版」モデル
model = genai.GenerativeModel('gemini-flash-latest')

# ニュースソース (4つ)
SOURCES = [
    {"name": "Bangkok Post", "url": "https://www.bangkokpost.com/rss/data/topstories.xml"},
    {"name": "The Pattaya News", "url": "https://thepattayanews.com/feed/"},
    {"name": "Pattaya Mail", "url": "https://www.pattayamail.com/feed"},
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
        if feed.bozo:
             print(f"警告: {source['name']} の取得に失敗した可能性があります。", flush=True)
        for entry in feed.entries:
            if count >= 3: break
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
あなたはタイ情勢に精通した日本語プロ編集者です。
12件程度のニュース見出しから、日本の読者やタイ在住者が最も関心を持つ「最高の一記事」を1件だけ厳選し、投稿文を作成してください。

【ニュースリスト】
{list_str}

【ライティングの絶対ルール】
・「AIらしさ」を徹底的に排除してください。
・「〜という重要なニュースです」「〜に注目しましょう」「〜をご存知ですか？」といったAI特有の「問いかけ」や「お決まりの結び」は一切禁止です。
・まるで現場をよく知る専門記者が、淡々と、かつ鋭い洞察を込めて書いているかのようなトーンにしてください。
・丁寧でありながら、読者におもねらないプロフェッショナルな文体。

[投稿文構成]
1. (ヘッドラインタイトル - 🚨や🇹🇭などの絵文字から開始)
2. (空白行)
3. (事実の要約：3行程度。余計な形容詞を削ぎ落とし、核心のみを伝える)
4. (空白行)
5. (本音の洞察/インパクト：1〜2行程度。現地在住の日本人が「あ、これは困るな/助かるな」と感じる実利的な視点。感情的なフレーズは避ける)

回答の最後に、必ず「INDEX:[番号]」とだけ書き添えてください。記事URLやハッシュタグは含めないでください。
例：INDEX:3
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
    """ユーザーIDを取得する。失敗した場合はエラーを表示"""
    if not THREADS_ACCESS_TOKEN:
        print("エラー: THREADS_ACCESS_TOKEN が設定されていません。")
        return None
    url = f"https://graph.threads.net/v1.0/me?fields=id&access_token={THREADS_ACCESS_TOKEN}"
    res = requests.get(url)
    if res.status_code == 200:
        return res.json().get('id')
    else:
        print(f"ユーザーID取得失敗: {res.text}")
        return None

def post_to_threads(text):
    global THREADS_USER_ID
    if not THREADS_USER_ID or THREADS_USER_ID == "":
        THREADS_USER_ID = get_threads_user_id()
        if not THREADS_USER_ID:
            print("投稿を中止します (ユーザーID不明)")
            return False
    
    # 1. コンテナ作成
    res_c = requests.post(f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads", data={
        "media_type": "TEXT", "text": text, "access_token": THREADS_ACCESS_TOKEN
    })
    if res_c.status_code != 200:
        print(f"コンテナ作成失敗: {res_c.text}")
        return False
    
    # 2. 公開
    creation_id = res_c.json().get('id')
    res_p = requests.post(f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish", data={
        "creation_id": creation_id, "access_token": THREADS_ACCESS_TOKEN
    })
    
    if res_p.status_code == 200:
        return True
    else:
        print(f"公開フェーズ失敗: {res_p.text}")
        return False

def main():
    print(f"--- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 定期実行開始 ---", flush=True)
    
    if not THREADS_ACCESS_TOKEN:
        print("【警告】THREADS_ACCESS_TOKEN が空です！GitHubのSecretsを確認してください。")
    
    articles = fetch_all_headlines()
    if not articles:
        print("新規記事がありませんでした。")
        return
        
    print(f"{len(articles)}件からAI記者が厳選中...", flush=True)
    post_content, selected_article = select_and_summarize(articles)
    if not post_content: return
    
    print("\n【決定した投稿案】\n" + post_content + "\n", flush=True)
    
    if post_to_threads(post_content):
        print("Threadsへの投稿に成功しました！ 🎉", flush=True)
        save_history(selected_article['link'])
    else:
        print("【最終結果】Threadsへの投稿に失敗しました。詳細なエラーは上記を確認してください。", flush=True)

if __name__ == "__main__":
    main()
