"""
問い合わせリプ検知
- 自分の投稿へのリプを取得
- 「聞きたい」「教えて」「相談」などのキーワードを検知
- 検知したらLINEに即通知
"""

import requests
import json
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from datetime import datetime

token = os.environ["THREADS_ACCESS_TOKEN"]
user_id = "34788313010783679"
INQUIRY_LOG = "inquiry_log.json"

# 問い合わせキーワード
INQUIRY_KEYWORDS = [
    "聞きたい", "教えて", "相談", "詳しく", "お願いしたい",
    "依頼", "お問い合わせ", "連絡", "DM", "どうすれば",
    "興味", "気になる", "話聞か", "お話", "サービス",
    "いくら", "料金", "費用", "頼みたい", "任せたい",
]

def get_recent_posts(limit=20):
    """直近の投稿を取得"""
    url = f"https://graph.threads.net/v1.0/{user_id}/threads"
    params = {
        "fields": "id,text,timestamp,permalink",
        "limit": limit,
        "access_token": token
    }
    res = requests.get(url, params=params).json()
    return res.get("data", [])

def get_replies(post_id):
    """投稿へのリプを取得"""
    url = f"https://graph.threads.net/v1.0/{post_id}/replies"
    params = {
        "fields": "id,text,timestamp,username",
        "access_token": token
    }
    res = requests.get(url, params=params).json()
    return res.get("data", [])

def is_inquiry(text):
    """問い合わせっぽいかどうか判定"""
    if not text:
        return False
    for kw in INQUIRY_KEYWORDS:
        if kw in text:
            return True
    return False

def load_inquiry_log():
    try:
        with open(INQUIRY_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_inquiry_log(log):
    with open(INQUIRY_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def send_line_message(text):
    """LINE通知"""
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    line_user = os.environ.get("LINE_USER_ID")
    if not line_token or not line_user:
        print("⚠️ LINE環境変数未設定")
        return
    res = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {line_token}",
            "Content-Type": "application/json"
        },
        json={"to": line_user, "messages": [{"type": "text", "text": text}]}
    )
    if res.status_code == 200:
        print("✅ LINE通知送信")
    else:
        print(f"⚠️ LINE通知失敗: {res.status_code}")

def run_inquiry_check():
    print("=" * 50)
    print(f"🔍 問い合わせリプ検知 - {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    print("=" * 50)

    log = load_inquiry_log()
    already_notified = {entry["reply_id"] for entry in log}

    posts = get_recent_posts(limit=20)
    new_inquiries = []

    for post in posts:
        post_id = post["id"]
        post_text = post.get("text", "")[:80]
        permalink = post.get("permalink", "")

        replies = get_replies(post_id)
        for reply in replies:
            reply_id = reply.get("id")
            reply_text = reply.get("text", "")
            username = reply.get("username", "不明")

            if reply_id in already_notified:
                continue

            if is_inquiry(reply_text):
                new_inquiries.append({
                    "reply_id": reply_id,
                    "username": username,
                    "reply_text": reply_text,
                    "post_text": post_text,
                    "permalink": permalink,
                    "detected_at": datetime.now().isoformat()
                })
                print(f"🎯 問い合わせ検知！@{username}: {reply_text[:60]}")

    if new_inquiries:
        # LINE通知
        lines = [f"🎯 問い合わせリプが{len(new_inquiries)}件来てます！\n"]
        for inq in new_inquiries:
            lines.append(
                f"👤 @{inq['username']}\n"
                f"💬 {inq['reply_text']}\n"
                f"📝 投稿: {inq['post_text']}...\n"
                f"🔗 {inq['permalink']}\n"
            )
        send_line_message("\n".join(lines))

        # ログ保存
        log.extend(new_inquiries)
        save_inquiry_log(log)
    else:
        print("問い合わせリプなし")

    return new_inquiries

if __name__ == "__main__":
    run_inquiry_check()
