# -*- coding: utf-8 -*-
import os
import sys
import json
import google.generativeai as genai
import requests
from dotenv import load_dotenv
from datetime import datetime

# Windows対応 (UTF-8強制)
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

# 設定 (GitHubのSecretsから読み込みます)
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN_EBI")
THREADS_USER_ID = os.getenv("THREADS_USER_ID_EBI")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY_EBI")
VERBLING_URL = "https://www.verbling.com/teachers/ebi"

# API初期化
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest')

def generate_lesson_post():
    """えび先生として日本語の学び直しに役立つポイントを生成"""
    
    prompt = f"""
あなたは情熱的で親しみやすい日本人教師「Sensei Ebi (えび先生)」です。
欧米の「日本語リスタート（学び直し）」層に向けて、
Threadsで「あ、また日本語をやりたい！」と思わせる短い投稿を作成してください。

[重要：文字数制限]
Threadsの制限があるため、必ず「英語・日本語・URLすべて含めて400文字程度」に収めてください。短く、力強く！

【投稿文の構成】
1. タイトル：(興味を引く英語と絵文字。例: 🌸 Re-start your Japanese!)
2. 本文（英語メイン）：教科書にはない、ネイティブが使う自然なニュアンスのコツを「1つだけ」簡潔に。
3. 日本語の例文：(短い日本文を1つ)
4. 応援メッセージ：(学び直しを肯定する短い一言)
5. 固定フレーズ：Don't let your Japanese fade away. Let's restart your journey.

【禁止事項】
・AI特有の「問いかけ」や「お決まりの結び」は禁止。プロフェッショナルな一人の教師として語る。
・絶対に長文にしないでください。
"""
    
    response = model.generate_content(prompt)
    post_content = response.text.strip()
    
    # 最後にVerblingへのリンクを追加
    post_content += f"\n\nBook a lesson with me on Verbling! 🍱👇\n{VERBLING_URL}"
    
    return post_content

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
    
    # 2. 公開
    creation_id = res_c.json().get('id')
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

    print("Generating post content...")
    post_content = generate_lesson_post()
    
    # 文字数チェック (簡易)
    print(f"Content Length: {len(post_content)}")
    
    print("\n[Generated Post]:")
    print(post_content)
    print("\nPosting to Threads...")
    
    if post_to_threads(post_content):
        print("Success! Posted to Sensei Ebi's Threads.")
    else:
        print("Failed to post.")

if __name__ == "__main__":
    main()
