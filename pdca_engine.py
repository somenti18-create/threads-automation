"""
PDCAエンジン
毎朝インサイトを取得 → 伸びた/伸びなかった分析 → 仮説生成 → 次の投稿に反映
"""

import requests
import json
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
PDCA_LOG = "pdca_log.json"

_claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

def _call_claude(prompt):
    msg = _claude.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text.strip()

# ───────────────────────────────
# 1. インサイト取得
# ───────────────────────────────

def get_recent_posts_with_insights(days=2):
    """直近の投稿とインサイトを取得"""
    url = f"https://graph.threads.net/v1.0/{user_id}/threads"
    params = {
        "fields": "id,text,timestamp",
        "limit": 30,
        "access_token": token
    }
    res = requests.get(url, params=params).json()
    posts = res.get("data", [])

    # 直近N日以内の投稿に絞る
    cutoff = datetime.utcnow() - timedelta(days=days)
    recent = []
    for p in posts:
        ts = datetime.strptime(p["timestamp"], "%Y-%m-%dT%H:%M:%S+0000")
        if ts >= cutoff:
            recent.append(p)

    # インサイト取得
    results = []
    for p in recent:
        ins_url = f"https://graph.threads.net/v1.0/{p['id']}/insights"
        ins_params = {
            "metric": "views,likes,replies,reposts,quotes",
            "access_token": token
        }
        ins = requests.get(ins_url, params=ins_params).json()

        stats = {"views": 0, "likes": 0, "replies": 0, "reposts": 0, "quotes": 0}
        if "data" in ins:
            for m in ins["data"]:
                val = m["values"][0]["value"] if m.get("values") else 0
                stats[m["name"]] = val

        # 問い合わせリプ検知
        inquiry_count = 0
        try:
            from inquiry_detector import get_replies, is_inquiry
            replies = get_replies(p["id"])
            inquiry_count = sum(1 for r in replies if is_inquiry(r.get("text", "")))
        except Exception:
            pass
        stats["inquiry_count"] = inquiry_count

        # エンゲージメント率計算（問い合わせリプは最重要指標として10倍）
        engagement = stats["likes"] + stats["replies"] * 2 + stats["reposts"] * 3 + inquiry_count * 10
        stats["engagement_score"] = engagement

        results.append({
            "id": p["id"],
            "text": p.get("text", ""),
            "timestamp": p["timestamp"],
            **stats
        })

    # エンゲージメント順にソート
    results.sort(key=lambda x: x["engagement_score"], reverse=True)
    return results

# ───────────────────────────────
# 2. Claude分析 → 仮説生成
# ───────────────────────────────

def analyze_and_generate_hypothesis(posts_with_insights):
    """投稿データをClaudeが分析して仮説を生成"""

    if not posts_with_insights:
        return None

    # トップ/ボトム投稿を抽出
    top = posts_with_insights[:3]
    bottom = posts_with_insights[-3:]

    # today_posts.jsonからタイプ情報を取得
    type_map = {}
    try:
        with open("today_posts.json", "r", encoding="utf-8") as f:
            today = json.load(f)
            for entry in today.get("log", []):
                for p in today.get("posts", []):
                    if p["index"] == entry.get("index"):
                        type_map[entry.get("post_id", "")] = p.get("label", "不明")
    except:
        pass

    top_text = "\n---\n".join([
        f"【{type_map.get(p['id'], '不明')}】{p['text'][:200]}\n【スコア】views:{p['views']} likes:{p['likes']} replies:{p['replies']} reposts:{p['reposts']} 問い合わせリプ:{p.get('inquiry_count', 0)}"
        for p in top
    ])
    bottom_text = "\n---\n".join([
        f"【{type_map.get(p['id'], '不明')}】{p['text'][:200]}\n【スコア】views:{p['views']} likes:{p['likes']} replies:{p['replies']} reposts:{p['reposts']} 問い合わせリプ:{p.get('inquiry_count', 0)}"
        for p in bottom
    ])

    # 時系列インサイトサマリーと各種分析を取得
    try:
        from insights_tracker import (
            get_summary_for_pdca, get_keyword_analysis,
            get_time_analysis, get_type_analysis,
            get_weekday_analysis, get_charcount_analysis,
            get_follower_trend
        )
        timeline_summary = get_summary_for_pdca(days=7)
        keyword_analysis = get_keyword_analysis(days=14)
        time_analysis = get_time_analysis(days=14)
        type_analysis = get_type_analysis(days=14)
        weekday_analysis = get_weekday_analysis(days=28)
        charcount_analysis = get_charcount_analysis(days=14)
        follower_trend = get_follower_trend()
    except Exception as e:
        print(f"⚠️ 分析取得エラー: {e}")
        timeline_summary = keyword_analysis = time_analysis = ""
        type_analysis = weekday_analysis = charcount_analysis = follower_trend = ""

    # 過去の仮説を読み込む
    past_hypotheses = load_past_hypotheses()
    past_text = ""
    if past_hypotheses:
        recent = past_hypotheses[-3:]
        past_text = "\n".join([
            f"- [{h['date']}] {h['hypothesis']} → 検証結果: {h.get('verified', '未検証')}"
            for h in recent
        ])

    prompt = f"""あなたはSNSマーケターのデータアナリストです。
以下のThreads投稿データを分析して、PDCAの「C（Check）→A（Act）」を行ってください。

{timeline_summary if timeline_summary else ""}
{keyword_analysis if keyword_analysis else ""}
{time_analysis if time_analysis else ""}
{type_analysis if type_analysis else ""}
{weekday_analysis if weekday_analysis else ""}
{charcount_analysis if charcount_analysis else ""}
{follower_trend if follower_trend else ""}


【エンゲージメント上位の投稿】
{top_text}

【エンゲージメント下位の投稿】
{bottom_text}

【過去の仮説と検証結果】
{past_text if past_text else "（まだデータなし）"}

以下の形式で出力してください：

## 今回の分析
- 伸びた理由（上位投稿の共通点）
- 伸びなかった理由（下位投稿の問題点）

## コンサル型 vs 実験者型の比較
- コンサル型の平均エンゲージメント
- 実験者型の平均エンゲージメント
- 今どちらが伸びているか・なぜか

## 過去仮説の検証
（過去の仮説が正しかったか、間違いだったかを評価）

## 問い合わせリプ分析
- 問い合わせリプが来た投稿の共通点（書き方・構成・テーマ）
- 問い合わせを引き出すために次回試すべき要素

## 次の投稿に向けた仮説（3つ）
1. 仮説: 〇〇すると伸びるはず / 理由: 〇〇 / 検証方法: 〇〇
2. 仮説: 〇〇すると伸びるはず / 理由: 〇〇 / 検証方法: 〇〇
3. 仮説: 〇〇すると伸びるはず / 理由: 〇〇 / 検証方法: 〇〇

## 次の投稿への具体的指示
（上の仮説を踏まえて、明日の投稿文生成時に必ず守るべきルール3〜5個。「問い合わせリプ1日2件」を目標に、読者が「詳しく聞きたい」と思うような投稿を意識すること）
"""

    return _call_claude(prompt)

# ───────────────────────────────
# 3. 仮説の保存・読み込み
# ───────────────────────────────

def save_hypothesis(analysis_text, posts_data):
    """仮説をログに保存"""
    log = load_pdca_log()

    entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "analysis": analysis_text,
        "hypothesis": extract_hypothesis(analysis_text),
        "top_post": posts_data[0]["text"][:100] if posts_data else "",
        "top_score": posts_data[0]["engagement_score"] if posts_data else 0,
        "verified": "未検証"
    }

    log.append(entry)

    with open(PDCA_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    print(f"✅ 仮説を {PDCA_LOG} に保存しました")
    return entry

def extract_hypothesis(analysis_text):
    """分析テキストから仮説部分を抽出"""
    lines = analysis_text.split("\n")
    hypotheses = []
    in_hypothesis = False
    for line in lines:
        if "次の投稿に向けた仮説" in line:
            in_hypothesis = True
        elif in_hypothesis and line.startswith("##"):
            break
        elif in_hypothesis and line.strip():
            hypotheses.append(line.strip())
    return " / ".join(hypotheses[:3])

def load_pdca_log():
    try:
        with open(PDCA_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def load_past_hypotheses():
    return load_pdca_log()

def get_current_instructions():
    """最新の仮説から投稿生成用の指示を取得"""
    log = load_pdca_log()
    if not log:
        return ""

    latest = log[-1]
    analysis = latest.get("analysis", "")

    # 「次の投稿への具体的指示」セクションを抽出
    lines = analysis.split("\n")
    instructions = []
    in_instructions = False
    for line in lines:
        if "次の投稿への具体的指示" in line:
            in_instructions = True
        elif in_instructions and line.startswith("##"):
            break
        elif in_instructions and line.strip():
            instructions.append(line.strip())

    return "\n".join(instructions)

# ───────────────────────────────
# 4. メイン実行
# ───────────────────────────────

def run_pdca():
    print("=" * 50)
    print(f"🔄 PDCA実行 - {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    print("=" * 50)

    # 時系列インサイトチェック（最新データを取得）
    try:
        from insights_tracker import run_insights_check, get_summary_for_pdca
        run_insights_check()
    except Exception as e:
        print(f"⚠️ 時系列チェックエラー: {e}")

    # インサイト取得
    print("\n📊 インサイト取得中...")
    posts = get_recent_posts_with_insights(days=3)

    if not posts:
        print("⚠️ 分析対象の投稿がありません")
        return

    print(f"\n分析対象: {len(posts)}本")
    for p in posts[:5]:
        print(f"  views:{p['views']:3d} likes:{p['likes']:2d} replies:{p['replies']:2d} | {p['text'][:40]}...")

    # Claude分析
    print("\n🤖 Claude分析中...")
    analysis = analyze_and_generate_hypothesis(posts)

    if not analysis:
        print("⚠️ 分析失敗")
        return

    print("\n" + "=" * 50)
    print("📋 分析結果")
    print("=" * 50)
    print(analysis)

    # 仮説保存
    save_hypothesis(analysis, posts)

    # ライティングスキルを自動更新
    update_writing_skills(analysis)

    # 次の投稿指示を取得して表示
    instructions = get_current_instructions()
    if instructions:
        print("\n" + "=" * 50)
        print("📌 次の投稿への指示")
        print("=" * 50)
        print(instructions)

    return analysis


def update_writing_skills(analysis_text):
    """PDCA分析を元に、既存ルール全体を見直して矛盾のない最新ルール一覧に再生成"""
    import re

    # 既存ルールを読み込む
    try:
        with open("writing_skills.json", "r", encoding="utf-8") as f:
            skills = json.load(f)
        existing_rules = skills.get("rules", [])
    except:
        existing_rules = []

    existing_text = "\n".join([f"- {r}" for r in existing_rules]) if existing_rules else "（まだルールなし）"

    prompt = f"""あなたはThreads投稿のライティングコーチです。

以下の「既存のライティングルール」と「今回のPDCA分析」を照らし合わせて、
矛盾・重複を解消した「最新の正しいルール一覧」を再生成してください。

【既存のライティングルール】
{existing_text}

【今回のPDCA分析】
{analysis_text}

条件：
- 既存ルールと新分析を統合して、矛盾がないルール一覧を作る
- 古いルールが新分析で否定された場合は新しいほうを採用する
- 具体的で実行可能な内容のみ
- 最大10個まで
- ルールの順番は重要度が高い順

JSON形式で出力してください：
{{"rules": ["ルール1", "ルール2", "..."]}}

JSONのみ出力してください。"""

    try:
        response = _call_claude(prompt)
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if not match:
            return
        data = json.loads(match.group())
        new_rules = data.get("rules", [])

        if not new_rules:
            return

        skills = {
            "rules": new_rules,
            "updated": datetime.now().strftime("%Y-%m-%d")
        }
        with open("writing_skills.json", "w", encoding="utf-8") as f:
            json.dump(skills, f, ensure_ascii=False, indent=2)

        print(f"\n✅ ライティングスキル再生成完了: {len(new_rules)}件")
        for r in new_rules:
            print(f"  ・{r}")

    except Exception as e:
        print(f"⚠️ ライティングスキル更新失敗: {e}")

if __name__ == "__main__":
    run_pdca()
