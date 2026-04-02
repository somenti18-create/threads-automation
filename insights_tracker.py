"""
投稿インサイト時系列トラッカー
投稿後 1時間・6時間・24時間のデータを収集して蓄積する
"""

import requests
import json
import os
from datetime import datetime, timedelta
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

token = os.environ["THREADS_ACCESS_TOKEN"]
HISTORY_FILE = "insights_history.json"
METRICS = ["views", "likes", "replies", "reposts", "quotes", "shares", "clicks"]
CHECK_HOURS = [1, 3, 6, 12, 24]


def get_insights(post_id):
    """1投稿のインサイトを取得"""
    res = requests.get(
        f"https://graph.threads.net/v1.0/{post_id}/insights",
        params={"metric": ",".join(METRICS), "access_token": token}
    ).json()

    stats = {m: 0 for m in METRICS}
    if "data" in res:
        for m in res["data"]:
            stats[m["name"]] = m["values"][0]["value"] if m.get("values") else 0
    return stats


def load_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def run_insights_check():
    """
    today_posts.json の投稿ログを見て
    1時間・6時間・24時間後のタイミングでインサイトを取得する
    """
    try:
        with open("today_posts.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        return

    log = data.get("log", [])
    posts = data.get("posts", [])
    if not log:
        return

    history = load_history()
    history_ids = {
        (entry["post_id"], entry["hours"]): True
        for entry in history
    }

    now = datetime.now()
    updated = False

    for entry in log:
        post_id = entry.get("post_id")
        posted_at = datetime.fromisoformat(entry["timestamp"])
        hours_elapsed = (now - posted_at).total_seconds() / 3600

        # 投稿テキストを取得
        post_text = ""
        for p in posts:
            if p["index"] == entry.get("index"):
                post_text = p["text"][:80]
                break

        for check_hour in CHECK_HOURS:
            # まだ計測タイミングが来ていない
            if hours_elapsed < check_hour:
                continue
            # 既に計測済み
            if (post_id, check_hour) in history_ids:
                continue

            # インサイト取得
            stats = get_insights(post_id)
            record = {
                "post_id": post_id,
                "post_text": post_text,
                "posted_at": entry["timestamp"],
                "hours": check_hour,
                "measured_at": now.isoformat(),
                **stats
            }
            history.append(record)
            history_ids[(post_id, check_hour)] = True
            updated = True
            print(f"📊 {check_hour}時間後計測: {post_text[:30]}... views:{stats['views']} likes:{stats['likes']}")

    if updated:
        save_history(history)
        print(f"✅ insights_history.json 更新")


def get_summary_for_pdca(days=7):
    """PDCA用：直近N日のインサイト集計サマリーを返す"""
    history = load_history()
    if not history:
        return ""

    cutoff = datetime.now() - timedelta(days=days)
    recent = [
        e for e in history
        if datetime.fromisoformat(e["posted_at"]) >= cutoff
    ]

    if not recent:
        return ""

    # 時間帯別平均
    by_hour = {}
    for h in CHECK_HOURS:
        records = [e for e in recent if e["hours"] == h]
        if not records:
            continue
        avg = {}
        for m in METRICS:
            avg[m] = round(sum(e.get(m, 0) for e in records) / len(records), 1)

        # 比率計算
        views = avg["views"] or 1  # ゼロ除算防止
        likes = avg["likes"] or 1
        avg["like_rate"] = round(avg["likes"] / views * 100, 2)      # 閲覧→いいね率(%)
        avg["reply_rate"] = round(avg["replies"] / views * 100, 2)    # 閲覧→リプ率(%)
        avg["reply_per_like"] = round(avg["replies"] / likes * 100, 2)  # いいね→リプ率(%)

        by_hour[h] = {"avg": avg, "count": len(records)}

    lines = [f"【直近{days}日間のインサイト時系列サマリー】"]
    for h, data in by_hour.items():
        avg = data["avg"]
        lines.append(
            f"\n▼ 投稿{h}時間後（{data['count']}投稿の平均）"
            f"\n  views:{avg['views']} likes:{avg['likes']} replies:{avg['replies']}"
            f" reposts:{avg['reposts']} quotes:{avg['quotes']} shares:{avg['shares']} clicks:{avg['clicks']}"
            f"\n  📊 閲覧→いいね率:{avg['like_rate']}% / 閲覧→リプ率:{avg['reply_rate']}% / いいね→リプ率:{avg['reply_per_like']}%"
        )

    # 伸びた投稿TOP3（24時間後のviews順）
    top = sorted(
        [e for e in recent if e["hours"] == 24],
        key=lambda x: x.get("views", 0),
        reverse=True
    )[:3]

    if top:
        lines.append("\n▼ 直近7日間 views TOP3（24時間後）")
        for i, p in enumerate(top, 1):
            lines.append(
                f"  {i}. views:{p['views']} likes:{p['likes']} replies:{p['replies']}\n"
                f"     「{p['post_text']}...」"
            )

    return "\n".join(lines)


def get_keyword_analysis(days=14):
    """キーワード別のインサイト平均を分析する"""
    import re
    history = load_history()
    if not history:
        return ""

    cutoff = datetime.now() - timedelta(days=days)
    # 24時間後データのみ使う（最終結果）
    records = [
        e for e in history
        if e["hours"] == 24 and datetime.fromisoformat(e["posted_at"]) >= cutoff
    ]

    if not records:
        return ""

    # 名詞・キーワード抽出（簡易：2文字以上の日本語単語）
    keyword_stats = {}
    for r in records:
        text = r.get("post_text", "")
        words = re.findall(r'[ぁ-んァ-ヶー一-龠]{2,6}', text)
        seen = set()
        for w in words:
            if w in seen:
                continue
            seen.add(w)
            if w not in keyword_stats:
                keyword_stats[w] = {"views": [], "likes": [], "replies": [], "count": 0}
            keyword_stats[w]["views"].append(r.get("views", 0))
            keyword_stats[w]["likes"].append(r.get("likes", 0))
            keyword_stats[w]["replies"].append(r.get("replies", 0))
            keyword_stats[w]["count"] += 1

    # 3投稿以上に登場したキーワードのみ集計
    results = []
    for word, stats in keyword_stats.items():
        if stats["count"] < 3:
            continue
        avg_views = sum(stats["views"]) / len(stats["views"])
        avg_likes = sum(stats["likes"]) / len(stats["likes"])
        avg_replies = sum(stats["replies"]) / len(stats["replies"])
        results.append({
            "word": word,
            "count": stats["count"],
            "avg_views": round(avg_views, 1),
            "avg_likes": round(avg_likes, 1),
            "avg_replies": round(avg_replies, 1),
        })

    if not results:
        return ""

    # views順にソート
    results.sort(key=lambda x: x["avg_views"], reverse=True)

    lines = [f"\n【キーワード別インサイト分析（直近{days}日・24時間後データ）】"]
    lines.append("▼ views平均が高いキーワード TOP10")
    for r in results[:10]:
        lines.append(
            f"  「{r['word']}」({r['count']}投稿) "
            f"views:{r['avg_views']} likes:{r['avg_likes']} replies:{r['avg_replies']}"
        )

    return "\n".join(lines)


if __name__ == "__main__":
    run_insights_check()
    print("\n" + get_summary_for_pdca())
    print(get_keyword_analysis())
