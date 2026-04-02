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
from inquiry_detector import run_inquiry_check

# 投稿時間パターン（UTC基準 = JST-9時間）
# JST 07:00 = UTC 22:00(前日), JST 08:30 = UTC 23:30(前日) → 繰り上げて翌日分で管理
# 実用的にUTC表記: JST07:00→22:00, JST08:30→23:30, JST10:00→01:00...
POST_TIMES = {
    "10posts": ["22:00", "23:30", "01:00", "02:30", "04:00", "06:00", "08:00", "10:00", "12:00", "13:30"],
    "5posts":  ["22:00", "01:00", "04:00", "08:00", "12:00"],
    "3posts":  ["22:00", "03:00", "12:00"],  # JST 7:00 / 12:00 / 21:00
}

# モード切替のしきい値
THRESHOLD_5 = 10000    # 1万で10→5投稿
THRESHOLD_3 = 100000   # 10万で5→3投稿

def get_mode():
    try:
        with open("mode.json", "r") as f:
            return json.load(f).get("mode", "3posts")
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
    """毎朝05:00 リサーチ→投稿文生成 (JST05:00 = UTC20:00)"""
    print(f"\n{'='*50}")
    print(f"🌅 朝のリサーチ - {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    print(f"{'='*50}")
    mode = get_mode()
    count = {"10posts": 10, "5posts": 5, "3posts": 3}.get(mode, 3)
    research(post_count=count)

def morning_report():
    """毎朝06:00 LINEにレポート送信 (JST06:00 = UTC21:00)"""
    print(f"\n📋 朝のレポート送信 - {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    run_daily_report()

def post_job():
    """投稿時間: 1本投稿"""
    mode = get_mode()
    print(f"\n📤 {datetime.now().strftime('%H:%M')} 投稿実行 [{mode}]")
    post_today_posts()

def nightly_pdca():
    """毎晩22:00 PDCA分析 (JST22:00 = UTC13:00)"""
    print(f"\n🔄 夜間PDCA - {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    analyze()
    run_pdca()
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

    # 毎朝リサーチ JST 05:00 = UTC 20:00
    schedule.every().day.at("20:00").do(morning_research)

    # 朝のレポート JST 06:00 = UTC 21:00
    schedule.every().day.at("21:00").do(morning_report)

    # 投稿スケジュール（1日10本・JST分散）
    for t in post_times:
        schedule.every().day.at(t).do(post_job)

    # 夜間PDCA JST 22:00 = UTC 13:00
    schedule.every().day.at("13:00").do(nightly_pdca)

    # 問い合わせリプ検知 2時間ごと
    schedule.every(2).hours.do(run_inquiry_check)

    print(f"\n待機中... (Ctrl+C で停止)\n")

def main():
    setup_schedule()

    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    main()
