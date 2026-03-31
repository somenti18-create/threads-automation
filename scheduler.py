import schedule
import time
import json
import os
from datetime import datetime
from research_threads import main as research
from post_to_threads import post_today_posts
from analyze_posts import analyze
from pdca_engine import run_pdca
from daily_report import run_daily_report

# 投稿時間パターン
POST_TIMES = {
    "10posts": ["07:00", "08:30", "10:00", "11:30", "13:00", "15:00", "17:00", "19:00", "21:00", "22:30"],
    "5posts":  ["07:00", "10:00", "13:00", "17:00", "21:00"],
    "3posts":  ["08:00", "13:00", "20:00"],
}

# モード切替のしきい値
THRESHOLD_5 = 10000    # 1万で10→5投稿
THRESHOLD_3 = 100000   # 10万で5→3投稿

def get_mode():
    try:
        with open("mode.json", "r") as f:
            return json.load(f).get("mode", "10posts")
    except:
        return "10posts"

def set_mode(mode):
    with open("mode.json", "w") as f:
        json.dump({"mode": mode, "updated": datetime.now().isoformat()}, f)

def check_and_switch_mode():
    """インサイトをチェックして自動モード切替"""
    try:
        with open("posts_data.json", "r", encoding="utf-8") as f:
            posts = json.load(f)
        max_views = max([p.get("views", 0) for p in posts], default=0)
        current_mode = get_mode()

        if max_views >= THRESHOLD_3 and current_mode != "3posts":
            set_mode("3posts")
            print(f"🎉 最高閲覧{max_views:,}達成！→ 3投稿モードに切替")
            reschedule()
        elif max_views >= THRESHOLD_5 and current_mode == "10posts":
            set_mode("5posts")
            print(f"🎉 最高閲覧{max_views:,}達成！→ 5投稿モードに切替")
            reschedule()
        else:
            print(f"📊 最高閲覧: {max_views:,} / モード: {current_mode}")
    except Exception as e:
        print(f"モード確認エラー: {e}")

def morning_research():
    """毎朝6:00 リサーチ→投稿文生成"""
    print(f"\n{'='*50}")
    print(f"🌅 朝のリサーチ - {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    print(f"{'='*50}")
    mode = get_mode()
    count = {"10posts": 10, "5posts": 5, "3posts": 3}[mode]
    research(post_count=count)

def post_job():
    """投稿時間: 1本投稿"""
    mode = get_mode()
    print(f"\n📤 {datetime.now().strftime('%H:%M')} 投稿実行 [{mode}]")
    post_today_posts()

def nightly_pdca():
    """毎晩22:00 デイリーレポート＋PDCA"""
    print(f"\n🔄 夜間PDCA - {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    analyze()
    run_pdca()
    run_daily_report()
    check_and_switch_mode()

def reschedule():
    """スケジュールをリセットして再設定"""
    schedule.clear()
    setup_schedule()

def setup_schedule():
    mode = get_mode()
    post_times = POST_TIMES[mode]

    print(f"\n🚀 スケジューラー起動")
    print(f"   モード: {mode} ({len(post_times)}投稿/日)")
    print(f"   投稿時間: {', '.join(post_times)}")

    # 毎朝リサーチ
    schedule.every().day.at("06:00").do(morning_research)

    # 投稿スケジュール
    for t in post_times:
        schedule.every().day.at(t).do(post_job)

    # 夜間PDCA＋デイリーレポート
    schedule.every().day.at("22:00").do(nightly_pdca)

    print(f"\n待機中... (Ctrl+C で停止)\n")

def main():
    setup_schedule()

    # 起動時に今日の投稿文がなければリサーチ実行
    if not os.path.exists("today_posts.json"):
        print("📝 投稿文がないためリサーチを実行します...")
        morning_research()

    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    main()
