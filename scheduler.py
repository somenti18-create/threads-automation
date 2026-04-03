import schedule
import time
import json
import os
from datetime import datetime

# タイムゾーンをUTCに強制（JST環境でもUTC基準で動かす）
os.environ["TZ"] = "UTC"
try:
    import time as _time
    _time.tzset()
except AttributeError:
    pass  # Windowsでは tzset 不要
from config import data_path
from research_threads import main as research
from post_to_threads import post_today_posts
from analyze_posts import analyze
from pdca_engine import run_pdca
from daily_report import run_daily_report
from inquiry_detector import run_inquiry_check
from insights_tracker import run_insights_check, record_follower_count

# 投稿時間パターン（UTC基準 = JST-9時間）
# JST 07:00 = UTC 22:00(前日), JST 08:30 = UTC 23:30(前日) → 繰り上げて翌日分で管理
# 実用的にUTC表記: JST07:00→22:00, JST08:30→23:30, JST10:00→01:00...
POST_TIMES = {
    "10posts": ["22:00", "23:30", "01:00", "02:30", "04:00", "06:00", "08:00", "10:00", "12:00", "13:30"],
    "5posts":  ["01:00", "04:00", "08:00", "10:00", "12:00"],  # JST 10:00/13:00/17:00/19:00/21:00
    "3posts":  ["22:00", "03:00", "12:00"],  # JST 7:00 / 12:00 / 21:00
}

# モード切替のしきい値
THRESHOLD_5 = 10000    # 1万で10→5投稿
THRESHOLD_3 = 100000   # 10万で5→3投稿

def get_mode():
    try:
        with open(data_path("mode.json"), "r") as f:
            return json.load(f).get("mode", "3posts")
    except:
        return "5posts"

def set_mode(mode):
    with open(data_path("mode.json"), "w") as f:
        json.dump({"mode": mode, "updated": datetime.now().isoformat()}, f)

def check_and_switch_mode():
    """インサイトをチェックして自動モード切替"""
    try:
        with open(data_path("posts_data.json"), "r", encoding="utf-8") as f:
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

def morning_pdca_and_research():
    """毎朝05:00 PDCA → skills更新 → 投稿文生成 (JST05:00 = UTC20:00)"""
    print(f"\n{'='*50}")
    print(f"🌅 朝のPDCA＆生成 - {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    print(f"{'='*50}")

    # 1. PDCA実行（skills更新まで含む）
    try:
        analyze()
        run_pdca()
        check_and_switch_mode()
        print("✅ PDCA完了")
    except Exception as e:
        print(f"⚠️ PDCAエラー: {e}")

    # 2. PDCA完了後に投稿文生成
    mode = get_mode()
    count = {"10posts": 10, "5posts": 5, "3posts": 3}.get(mode, 3)
    research(post_count=count)

def morning_report():
    """毎朝06:00 LINEにレポート送信 (JST06:00 = UTC21:00)"""
    print(f"\n📋 朝のレポート送信 - {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    run_daily_report()

def post_job():
    """投稿時間: 1本投稿（POSTING_ENABLED=falseで停止）"""
    if os.environ.get("POSTING_ENABLED", "true").lower() == "false":
        print(f"\n⏸️ 投稿停止中 (POSTING_ENABLED=false)")
        return
    mode = get_mode()
    print(f"\n📤 {datetime.now().strftime('%H:%M')} 投稿実行 [{mode}]")
    post_today_posts()

def nightly_pdca():
    """※廃止 - PDCAは朝05:00に移動"""
    pass

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

    # 毎朝 PDCA→生成 JST 05:00 = UTC 20:00
    schedule.every().day.at("20:00").do(morning_pdca_and_research)

    # 朝のレポート JST 06:00 = UTC 21:00
    schedule.every().day.at("21:00").do(morning_report)

    # 投稿スケジュール JST 07:00〜 (UTC 22:00〜)
    for t in post_times:
        schedule.every().day.at(t).do(post_job)

    # 問い合わせリプ検知 2時間ごと
    schedule.every(2).hours.do(run_inquiry_check)

    # インサイト時系列チェック 1時間ごと
    schedule.every(1).hours.do(run_insights_check)

    # フォロワー数記録 月曜朝（UTC 20:00 = JST 05:00）週1回
    schedule.every().monday.at("20:00").do(record_follower_count)

    print(f"\n待機中... (Ctrl+C で停止)\n")

def ensure_today_posts():
    """起動時にtoday_posts.jsonが空なら即生成（デプロイ後の復旧用）"""
    try:
        with open("today_posts.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        today = datetime.now().strftime("%Y-%m-%d")
        if data.get("date") == today and data.get("posts"):
            print(f"✅ today_posts.json 確認済み ({len(data['posts'])}本)")
            return
    except Exception:
        pass

    print("⚠️ today_posts.jsonが空 → 今日の投稿を即生成します")
    mode = get_mode()
    count = {"10posts": 10, "5posts": 5, "3posts": 3}.get(mode, 5)
    research(post_count=count)

def main():
    setup_schedule()
    ensure_today_posts()

    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    main()
