import requests
import json
from datetime import datetime
from dotenv import dotenv_values

config = dotenv_values(".env")
token = config["THREADS_ACCESS_TOKEN"]
user_id = "34788313010783679"

def create_post(text):
    """Threadsに投稿する"""

    # Step1: メディアコンテナ作成
    url = f"https://graph.threads.net/v1.0/{user_id}/threads"
    params = {
        "media_type": "TEXT",
        "text": text,
        "access_token": token
    }
    res = requests.post(url, params=params)
    data = res.json()

    if "id" not in data:
        print(f"❌ コンテナ作成失敗: {data}")
        return None

    container_id = data["id"]

    # Step2: 公開
    publish_url = f"https://graph.threads.net/v1.0/{user_id}/threads_publish"
    publish_params = {
        "creation_id": container_id,
        "access_token": token
    }
    pub_res = requests.post(publish_url, params=publish_params)
    pub_data = pub_res.json()

    if "id" in pub_data:
        print(f"✅ 投稿成功: {pub_data['id']}")
        return pub_data["id"]
    else:
        print(f"❌ 投稿失敗: {pub_data}")
        return None

def post_today_posts():
    """today_posts.json の投稿を1本だけ投稿する（スケジューラーから呼ばれる）"""
    try:
        with open("today_posts.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("❌ today_posts.json が見つかりません。先にリサーチを実行してください。")
        return

    posts = data.get("posts", [])
    posted = data.get("posted", [])

    # まだ投稿していないものを探す
    unposted = [p for p in posts if p["index"] not in posted]

    if not unposted:
        print("📭 今日の投稿は全て完了しています")
        return

    # 次の1本を投稿
    next_post = unposted[0]
    print(f"\n投稿 {next_post['index']}/5")
    print(next_post["text"])
    print()

    post_id = create_post(next_post["text"])

    if post_id:
        # 投稿済みとしてマーク
        posted.append(next_post["index"])
        data["posted"] = posted

        # 投稿ログ保存
        if "log" not in data:
            data["log"] = []
        data["log"].append({
            "index": next_post["index"],
            "post_id": post_id,
            "timestamp": datetime.now().isoformat()
        })

        with open("today_posts.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"残り {len(unposted) - 1} 本")

if __name__ == "__main__":
    post_today_posts()
