from config import data_path
import requests
import json
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

token = os.environ["THREADS_ACCESS_TOKEN"]
user_id = "34788313010783679"

def get_posts():
    """過去の投稿を取得"""
    url = f"https://graph.threads.net/v1.0/{user_id}/threads"
    params = {
        "fields": "id,text,timestamp,media_type,permalink",
        "limit": 20,
        "access_token": token
    }
    response = requests.get(url, params=params)
    return response.json()

def get_insights(post_id):
    """各投稿のインサイトを取得"""
    url = f"https://graph.threads.net/v1.0/{post_id}/insights"
    params = {
        "metric": "views,likes,replies,reposts,quotes",
        "access_token": token
    }
    response = requests.get(url, params=params)
    return response.json()

def analyze():
    print("=" * 50)
    print("📊 Threads 投稿分析レポート")
    print("=" * 50)

    posts_data = get_posts()

    if "error" in posts_data:
        print("エラー:", posts_data["error"])
        return

    posts = posts_data.get("data", [])
    print(f"\n取得した投稿数: {len(posts)}件\n")

    all_stats = []

    for i, post in enumerate(posts):
        post_id = post["id"]
        text = post.get("text", "（テキストなし）")
        timestamp = post.get("timestamp", "")
        permalink = post.get("permalink", "")

        # インサイト取得
        insights = get_insights(post_id)

        stats = {"views": 0, "likes": 0, "replies": 0, "reposts": 0, "quotes": 0}
        if "data" in insights:
            for metric in insights["data"]:
                name = metric["name"]
                value = metric["values"][0]["value"] if metric.get("values") else 0
                stats[name] = value

        all_stats.append({**post, **stats})

        print(f"【投稿 {i+1}】{timestamp[:10] if timestamp else '日付不明'}")
        print(f"  本文: {text[:60]}{'...' if len(text) > 60 else ''}")
        print(f"  👁 表示: {stats['views']}  ❤️ いいね: {stats['likes']}  💬 返信: {stats['replies']}  🔁 リポスト: {stats['reposts']}")
        print(f"  URL: {permalink}")
        print()

    # サマリー
    if all_stats:
        print("=" * 50)
        print("📈 サマリー")
        print("=" * 50)
        total_views = sum(p["views"] for p in all_stats)
        total_likes = sum(p["likes"] for p in all_stats)
        total_replies = sum(p["replies"] for p in all_stats)

        best_post = max(all_stats, key=lambda x: x["likes"])

        print(f"合計表示数: {total_views:,}")
        print(f"合計いいね: {total_likes:,}")
        print(f"合計返信数: {total_replies:,}")
        print(f"\n🏆 最もいいねが多い投稿:")
        print(f"  {best_post.get('text', '')[:80]}")
        print(f"  ❤️ {best_post['likes']} いいね  👁 {best_post['views']} 表示")

    # JSONで保存
    with open(data_path("posts_data.json"), "w", encoding="utf-8") as f:
        json.dump(all_stats, f, ensure_ascii=False, indent=2)
    print("\n✅ 詳細データを posts_data.json に保存しました")

if __name__ == "__main__":
    analyze()
