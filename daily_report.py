from config import data_path
"""
1日1回レポート生成
- その日の投稿の意図と結果
- 反省点
- 翌日の施策
- 壁打ち用の問いかけ
"""

import json
import requests
import os
import anthropic
from datetime import datetime, timedelta
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

token = os.environ["THREADS_ACCESS_TOKEN"]
user_id = "34788313010783679"
REPORT_LOG = data_path("report_log.json")

_claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

def _call_claude(prompt):
    msg = _claude.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text.strip()

def get_today_posts_with_insights():
    """前日投稿した内容とインサイトを取得（朝レポートはyesterday_posts.jsonを優先）"""
    # 朝レポートはPDCAでtoday_posts.jsonがリセットされた後に走るため
    # 前日分をyesterday_posts.jsonから読む
    for fname in ("yesterday_posts.json", "today_posts.json"):
        try:
            with open(fname, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("log"):  # 投稿済みデータがあるものを使う
                break
        except:
            data = None
    if not data:
        return []

    log = data.get("log", [])
    posts_with_insights = []

    for entry in log:
        post_id = entry.get("post_id")
        if not post_id:
            continue

        # インサイト取得
        url = f"https://graph.threads.net/v1.0/{post_id}/insights"
        params = {
            "metric": "views,likes,replies,reposts,quotes",
            "access_token": token
        }
        res = requests.get(url, params=params).json()

        stats = {"views": 0, "likes": 0, "replies": 0, "reposts": 0}
        if "data" in res:
            for m in res["data"]:
                val = m["values"][0]["value"] if m.get("values") else 0
                stats[m["name"]] = val

        # 投稿文を取得
        post_index = entry.get("index", 0)
        post_text = ""
        for p in data.get("posts", []):
            if p["index"] == post_index:
                post_text = p["text"]
                break

        posts_with_insights.append({
            "index": post_index,
            "text": post_text,
            "timestamp": entry.get("timestamp", ""),
            **stats
        })

    return posts_with_insights

def get_pdca_log():
    try:
        with open(data_path("pdca_log.json"), "r", encoding="utf-8") as f:
            log = json.load(f)
            return log[-1] if log else {}
    except:
        return {}

def generate_report(posts_with_insights):
    """Claudeがレポートを生成"""

    if not posts_with_insights:
        return "今日の投稿データがまだありません。"

    posts_summary = "\n---\n".join([
        f"投稿{p['index']}本目\n"
        f"本文: {p['text'][:150]}\n"
        f"views:{p['views']} likes:{p['likes']} replies:{p['replies']} reposts:{p['reposts']}"
        for p in posts_with_insights
    ])

    total_views = sum(p["views"] for p in posts_with_insights)
    total_likes = sum(p["likes"] for p in posts_with_insights)
    total_replies = sum(p["replies"] for p in posts_with_insights)
    best = max(posts_with_insights, key=lambda x: x["views"]) if posts_with_insights else {}

    pdca = get_pdca_log()
    yesterday_instructions = pdca.get("analysis", "（まだデータなし）")[:500]

    prompt = f"""あなたはSNSマーケターのコーチです。
以下は小野寺壮史（@line_polynk / SNS運用×AI自動化）の今日のThreads運用データです。

【今日の投稿と結果】
{posts_summary}

【今日の合計】
- 総表示数: {total_views}
- 総いいね: {total_likes}
- 総返信: {total_replies}
- 最高表示投稿: {best.get('text', '')[:80]}（{best.get('views', 0)} views）

【今日の投稿方針（前日PDCAより）】
{yesterday_instructions}

以下の形式でレポートを作成してください。
マークダウンは使わず、シンプルで読みやすい文章で書いてください。

━━━━━━━━━━━━━━━━━━━━
📊 今日の運用レポート（{datetime.now().strftime('%Y/%m/%d')}）
━━━━━━━━━━━━━━━━━━━━

【今日の数字】
（合計表示・いいね・返信・ベスト投稿を記載）

【今日の意図と結果】
（今日どんな狙いで投稿したか、結果はどうだったか）

【よかった点】
（伸びた投稿の要因分析）

【反省点】
（伸びなかった投稿の問題点）

【明日の施策】
（明日試すべき具体的なこと3つ）

【壁打ちしたいこと】
（あなたが小野寺さんに投げかけたい問いや仮説を1〜2個。一緒に考えたいトピック）

━━━━━━━━━━━━━━━━━━━━
"""

    return _call_claude(prompt)

def send_line_message(text):
    """LINE Messaging APIでメッセージ送信"""
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if not token or not user_id:
        print("⚠️ LINE環境変数未設定、スキップ")
        return

    # LINEは1メッセージ5000文字制限のため分割
    max_len = 4900
    chunks = [text[i:i+max_len] for i in range(0, len(text), max_len)]

    for chunk in chunks:
        res = requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "to": user_id,
                "messages": [{"type": "text", "text": chunk}]
            }
        )
        if res.status_code == 200:
            print("✅ LINEに送信しました")
        else:
            print(f"⚠️ LINE送信失敗: {res.status_code} {res.text}")

def save_report(report_text):
    """レポートをログに保存"""
    try:
        with open(REPORT_LOG, "r", encoding="utf-8") as f:
            log = json.load(f)
    except:
        log = []

    log.append({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "report": report_text
    })

    with open(REPORT_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def run_daily_report():
    print("\n" + "=" * 50)
    print(f"📋 デイリーレポート生成中...")
    print("=" * 50 + "\n")

    posts = get_today_posts_with_insights()
    report = generate_report(posts)

    print(report)
    save_report(report)
    send_line_message(report)

    print("\n\n" + "=" * 50)
    print("💬 壁打ちしますか？（返答してください）")
    print("=" * 50)

    return report

if __name__ == "__main__":
    run_daily_report()
