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

# 設定
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
あなたは日本人教師「Sensei Ebi (えび先生)」です。
欧米の日本語学び直し層に向けて、Threadsで日本語の短文レッスンを投稿してください。

[重要：文字数制限]
Threadsの制限があるため、必ず「英語・日本語すべて含めて350文字程度」に収めてください。短くインパクト重視！

【投稿構成】
1. タイトル：興味を引く英語と絵文字
2. 本文（英語メイン）：ネイティブの自然なコツを1つだけ、簡潔に説明。
3. 日本語の例文：(1つ)
4. 応援メッセージ：(短い一言)
5. 固定フレーズ：Don't let your Japanese fade away. Let's restart your journey.

【禁止事項】
・AI特有の回答（問いかけなど）は不要。一人のプロ教師として語る。
・不必要なハッシュタグや、example.com等の架空のURLは含めないでください。
"""
    
    response = model.generate_content(prompt)
    post_content = response.text.strip()
    
    # 最後にVerblingへのリンクを追加
    post_content += f"\n\nBook a lesson with me on Verbling! 🍱👇\n{VERBLING_URL}"
    
    # 【安全装置】500文字を超えていたら、末尾を削る（Threadsの制限対策）
    if len(post_content) > 500:
        post_content = post_content[:497] + "..."
    
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
    
    print(f"Final Content Length: {len(post_content)}")
    print("\n[Generated Post]:")
    print(post_content)
    print("\nPosting to Threads...")
    
    if post_to_threads(post_content):
        print("Success! Posted to Sensei Ebi's Threads.")
    else:
        print("Failed to post.")

if __name__ == "__main__":
    main()
