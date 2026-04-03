from config import data_path
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
HISTORY_FILE = data_path("insights_history.json")
METRICS = ["views", "likes", "replies", "reposts", "quotes", "shares", "clicks"]
CHECK_HOURS = [1, 3, 6, 12, 24, 48, 168]  # 168h = 1week


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
        with open(data_path("today_posts.json"), "r", encoding="utf-8") as f:
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

            # 投稿タイプ・variant・hypothesis_idを取得
            post_type = ""
            post_char_count = 0
            variant = ""
            hypothesis_id = ""
            for p in posts:
                if p["index"] == entry.get("index"):
                    post_type = p.get("label", "")
                    post_char_count = len(p.get("text", ""))
                    variant = p.get("variant", "")
                    hypothesis_id = p.get("hypothesis_id", "")
                    break

            # 投稿時間帯・曜日
            jst_hour = (posted_at.hour + 9) % 24
            weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
            weekday = weekday_names[posted_at.weekday()]

            # インサイト取得
            stats = get_insights(post_id)
            record = {
                "post_id": post_id,
                "post_text": post_text,
                "post_type": post_type,
                "post_char_count": post_char_count,
                "posted_at": entry["timestamp"],
                "jst_hour": jst_hour,
                "weekday": weekday,
                "hours": check_hour,
                "measured_at": now.isoformat(),
                "variant": variant,
                "hypothesis_id": hypothesis_id,
                **stats
            }
            history.append(record)
            history_ids[(post_id, check_hour)] = True
            updated = True
            print(f"📊 {check_hour}時間後計測: {post_text[:30]}... views:{stats['views']} likes:{stats['likes']}")
            # Googleスプレッドシートに書き込み
            try:
                from sheets_logger import log_insight
                log_insight(record)
            except Exception:
                pass

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

    # 伸び計測（各ポイント間の増加量）
    hour_list = sorted(by_hour.keys())
    if len(hour_list) >= 2:
        lines.append("\n▼ 時間帯別 views 伸び（平均）")
        for i in range(1, len(hour_list)):
            h_prev = hour_list[i - 1]
            h_curr = hour_list[i]
            if h_prev in by_hour and h_curr in by_hour:
                diff = round(by_hour[h_curr]["avg"]["views"] - by_hour[h_prev]["avg"]["views"], 1)
                lines.append(f"  {h_prev}h→{h_curr}h: +{diff} views")

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


def get_time_analysis(days=14):
    """投稿時間帯別パフォーマンス分析（24時間後データ）"""
    history = load_history()
    if not history:
        return ""

    cutoff = datetime.now() - timedelta(days=days)
    records = [
        e for e in history
        if e["hours"] == 24 and datetime.fromisoformat(e["posted_at"]) >= cutoff
        and "jst_hour" in e
    ]
    if not records:
        return ""

    hour_stats = {}
    for r in records:
        h = r["jst_hour"]
        if h not in hour_stats:
            hour_stats[h] = {"views": [], "likes": [], "replies": []}
        hour_stats[h]["views"].append(r.get("views", 0))
        hour_stats[h]["likes"].append(r.get("likes", 0))
        hour_stats[h]["replies"].append(r.get("replies", 0))

    lines = [f"\n【投稿時間帯別パフォーマンス（直近{days}日・24時間後）】"]
    for h in sorted(hour_stats.keys()):
        s = hour_stats[h]
        n = len(s["views"])
        avg_v = round(sum(s["views"]) / n, 1)
        avg_l = round(sum(s["likes"]) / n, 1)
        avg_r = round(sum(s["replies"]) / n, 1)
        lines.append(f"  JST {h:02d}時台 ({n}投稿): views:{avg_v} likes:{avg_l} replies:{avg_r}")

    return "\n".join(lines)


def get_type_analysis(days=14):
    """投稿タイプ別パフォーマンス比較（24時間後データ）"""
    history = load_history()
    if not history:
        return ""

    cutoff = datetime.now() - timedelta(days=days)
    records = [
        e for e in history
        if e["hours"] == 24 and datetime.fromisoformat(e["posted_at"]) >= cutoff
        and e.get("post_type")
    ]
    if not records:
        return ""

    type_stats = {}
    for r in records:
        t = r["post_type"]
        if t not in type_stats:
            type_stats[t] = {"views": [], "likes": [], "replies": []}
        type_stats[t]["views"].append(r.get("views", 0))
        type_stats[t]["likes"].append(r.get("likes", 0))
        type_stats[t]["replies"].append(r.get("replies", 0))

    lines = [f"\n【投稿タイプ別パフォーマンス（直近{days}日・24時間後）】"]
    for t, s in type_stats.items():
        n = len(s["views"])
        avg_v = round(sum(s["views"]) / n, 1)
        avg_l = round(sum(s["likes"]) / n, 1)
        avg_r = round(sum(s["replies"]) / n, 1)
        lines.append(f"  【{t}】({n}投稿): views:{avg_v} likes:{avg_l} replies:{avg_r}")

    return "\n".join(lines)


def get_weekday_analysis(days=28):
    """曜日別パフォーマンス分析（24時間後データ）"""
    history = load_history()
    if not history:
        return ""

    cutoff = datetime.now() - timedelta(days=days)
    records = [
        e for e in history
        if e["hours"] == 24 and datetime.fromisoformat(e["posted_at"]) >= cutoff
        and e.get("weekday")
    ]
    if not records:
        return ""

    weekday_order = ["月", "火", "水", "木", "金", "土", "日"]
    day_stats = {d: {"views": [], "likes": [], "replies": []} for d in weekday_order}
    for r in records:
        d = r["weekday"]
        if d in day_stats:
            day_stats[d]["views"].append(r.get("views", 0))
            day_stats[d]["likes"].append(r.get("likes", 0))
            day_stats[d]["replies"].append(r.get("replies", 0))

    lines = [f"\n【曜日別パフォーマンス（直近{days}日・24時間後）】"]
    for d in weekday_order:
        s = day_stats[d]
        if not s["views"]:
            continue
        n = len(s["views"])
        avg_v = round(sum(s["views"]) / n, 1)
        avg_l = round(sum(s["likes"]) / n, 1)
        avg_r = round(sum(s["replies"]) / n, 1)
        lines.append(f"  {d}曜日 ({n}投稿): views:{avg_v} likes:{avg_l} replies:{avg_r}")

    return "\n".join(lines)


def get_charcount_analysis(days=14):
    """投稿文字数と数値の相関分析（24時間後データ）"""
    history = load_history()
    if not history:
        return ""

    cutoff = datetime.now() - timedelta(days=days)
    records = [
        e for e in history
        if e["hours"] == 24 and datetime.fromisoformat(e["posted_at"]) >= cutoff
        and e.get("post_char_count", 0) > 0
    ]
    if not records:
        return ""

    # 文字数をバケットに分類
    buckets = {"〜80字": [], "81〜130字": [], "131〜200字": [], "201字〜": []}
    for r in records:
        c = r["post_char_count"]
        if c <= 80:
            buckets["〜80字"].append(r)
        elif c <= 130:
            buckets["81〜130字"].append(r)
        elif c <= 200:
            buckets["131〜200字"].append(r)
        else:
            buckets["201字〜"].append(r)

    lines = [f"\n【文字数別パフォーマンス（直近{days}日・24時間後）】"]
    for label, recs in buckets.items():
        if not recs:
            continue
        n = len(recs)
        avg_v = round(sum(r.get("views", 0) for r in recs) / n, 1)
        avg_l = round(sum(r.get("likes", 0) for r in recs) / n, 1)
        avg_r = round(sum(r.get("replies", 0) for r in recs) / n, 1)
        lines.append(f"  {label} ({n}投稿): views:{avg_v} likes:{avg_l} replies:{avg_r}")

    return "\n".join(lines)


FOLLOWER_FILE = "follower_history.json"


def record_follower_count():
    """フォロワー数を記録（週1回呼ぶ）"""
    token_val = token
    user_id = "34788313010783679"
    try:
        res = requests.get(
            f"https://graph.threads.net/v1.0/{user_id}",
            params={"fields": "followers_count", "access_token": token_val}
        ).json()
        count = res.get("followers_count", 0)
        if count == 0:
            return

        try:
            with open(FOLLOWER_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except:
            history = []

        history.append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "followers": count
        })

        with open(FOLLOWER_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

        print(f"👥 フォロワー数記録: {count:,}")
        # Googleスプレッドシートに書き込み
        try:
            from sheets_logger import log_follower
            log_follower(count)
        except Exception:
            pass
    except Exception as e:
        print(f"⚠️ フォロワー記録エラー: {e}")


def get_follower_trend():
    """フォロワー数の推移サマリー"""
    try:
        with open(FOLLOWER_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    except:
        return ""

    if len(history) < 2:
        return ""

    recent = history[-8:]  # 直近8週分
    lines = ["\n【フォロワー数の推移】"]
    for i, entry in enumerate(recent):
        diff = ""
        if i > 0:
            delta = entry["followers"] - recent[i - 1]["followers"]
            diff = f" ({'+' if delta >= 0 else ''}{delta:,})"
        lines.append(f"  {entry['date']}: {entry['followers']:,}人{diff}")

    return "\n".join(lines)


if __name__ == "__main__":
    run_insights_check()
    print("\n" + get_summary_for_pdca())
    print(get_keyword_analysis())
    print(get_time_analysis())
    print(get_type_analysis())
    print(get_weekday_analysis())
    print(get_charcount_analysis())
    print(get_follower_trend())
