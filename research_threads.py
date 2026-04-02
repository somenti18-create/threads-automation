import json
import re
import os
import time
import requests
import anthropic
from datetime import datetime
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

_claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

def _call_claude(prompt):
    msg = _claude.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text.strip()

# PDCAエンジンから最新指示を取得
def get_pdca_instructions():
    try:
        from pdca_engine import get_current_instructions
        return get_current_instructions()
    except:
        return ""

# ライティングスキルを読み込む
def get_writing_skills():
    try:
        with open("writing_skills.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            target = data.get("target", "")
            rules = data.get("rules", [])
            rules_text = "\n".join([f"- {r}" for r in rules])
            if target:
                return f"【ターゲット】{target}\n\n【ルール】\n{rules_text}"
            return rules_text
    except:
        return ""

KEYWORDS = [
    "Threads運用",
    "TikTok運用",
    "YouTube運用",
    "SNSマーケティング",
    "SNS集客",
    "集客自動化",
    "LINE運用",
    "LINEマーケティング",
    "AI自動化",
    "AI活用",
    "業務自動化",
    "業務効率化",
    "売上アップ",
    "売上改善",
    "中小企業 集客",
    "スクール集客",
    "飲食店集客",
    "店舗集客",
    "リピーター獲得",
    "新規顧客獲得",
    "フリーランス",
]

# 投稿タイプ定義（コンサル型 vs 実験者型を混ぜてPDCAで検証）
POST_TYPES = [
    {"type": "consultant", "label": "コンサル型", "description": "クライアントの実績・支援事例を語る。月商70万→700万などの結果を主役にする"},
    {"type": "experimenter", "label": "実験者型", "description": "自分が実験台。このシステム構築・AI自動化・Threads運用の試行錯誤をリアルに語る"},
    {"type": "consultant", "label": "コンサル型", "description": "SNS×売上向上のノウハウ・知識を提供する。読者が「なるほど」と思える知見"},
    {"type": "experimenter", "label": "実験者型", "description": "今日の失敗・気づき・驚いた結果をリアルタイムで報告する形式"},
    {"type": "consultant", "label": "コンサル型", "description": "よくある間違い（❌）と正解（✅）を対比で見せる教育型"},
    {"type": "experimenter", "label": "実験者型", "description": "AIやClaudeで自動化した具体的な話。何時間が何分になったなどの数字を出す"},
    {"type": "consultant", "label": "コンサル型", "description": "共感型。経営者・SNS担当者が「あるある」と思う悩みを代弁してから解決策を示す"},
    {"type": "experimenter", "label": "実験者型", "description": "Threadsで実際に試した投稿の結果報告。伸びた理由・伸びなかった理由を分析して公開"},
    {"type": "consultant", "label": "コンサル型", "description": "POLYNKの価値観・ミッションを語る。数字より売上、SNSは手段という想い"},
    {"type": "experimenter", "label": "実験者型", "description": "24歳がAIで仕事を自動化していくリアルな過程。今日何を作ったか・何が変わったか"},
]

PROFILE = """
名前: 小野寺壮史 / POLYNK (@line_polynk)
ビジネス:
- 個人事業主・小規模店舗向けSNS運用代行（LINE / Threads / YouTube / TikTok）
- 業務効率化・自動化代行（Claude Codeでシステム構築）
  → LINE自動化・Threads自動投稿・請求書自動作成など
差別化: SNSのフォロワー数ではなく「売上に直結する導線設計」にフォーカス
実績:
- 整体・サロン・飲食など個人店のLINE×SNS導線を構築
- 支援先の月商を平均4〜7倍に改善
- 月商70万→490万、100万→700万など
支援内容: LINE導線設計・ステップ配信・SNS集客・AI業務自動化
ターゲット: 整体・サロン・飲食・個人店のオーナー
"""

def scrape_threads(keyword, max_posts=8):
    """ApifyでThreadsのキーワード検索して投稿を収集"""
    apify_token = os.environ.get("APIFY_API_TOKEN")
    if not apify_token:
        print("⚠️ APIFY_API_TOKEN未設定")
        return []

    try:
        # Actorを非同期で起動
        run_res = requests.post(
            "https://api.apify.com/v2/acts/futurizerush~threads-keyword-search/runs",
            headers={"Authorization": f"Bearer {apify_token}"},
            json={"keywords": [keyword], "maxResults": "10", "sortBy": "top"},
            timeout=30
        )
        run_data = run_res.json()
        run_id = run_data.get("data", {}).get("id")
        if not run_id:
            print(f"⚠️ Apify起動失敗: {run_data}")
            return []

        # 完了待ち（最大120秒）
        for _ in range(24):
            time.sleep(5)
            status_res = requests.get(
                f"https://api.apify.com/v2/actor-runs/{run_id}",
                headers={"Authorization": f"Bearer {apify_token}"}
            ).json()
            status = status_res.get("data", {}).get("status")
            if status == "SUCCEEDED":
                break
            elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                print(f"⚠️ Apify実行失敗: {status}")
                return []

        # データ取得
        dataset_id = status_res.get("data", {}).get("defaultDatasetId")
        items_res = requests.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items",
            headers={"Authorization": f"Bearer {apify_token}"},
            params={"format": "json"}
        ).json()

        posts = []
        for item in items_res[:max_posts]:
            text = item.get("text") or item.get("content") or ""
            if text:
                posts.append({
                    "text": text,
                    "likes": item.get("likeCount", 0),
                    "replies": item.get("replyCount", 0),
                })
        print(f"  {keyword}: {len(posts)}件取得")
        return posts

    except Exception as e:
        print(f"⚠️ スクレイピングエラー ({keyword}): {e}")
        return []

def generate_post_from_research(research_posts, post_index):
    """リサーチ結果を元にClaudeで投稿文を生成"""
    post_type_info = POST_TYPES[post_index % len(POST_TYPES)]
    style = f"【{post_type_info['label']}】{post_type_info['description']}"

    # PDCAからの最新指示を取得
    pdca_instructions = get_pdca_instructions()
    pdca_section = f"""
【PDCAからの指示（必ず守ること）】
{pdca_instructions}
""" if pdca_instructions else ""

    # ライティングスキルを取得
    writing_skills = get_writing_skills()
    skills_section = f"""
【蓄積されたライティングルール（必ず守ること）】
{writing_skills}
""" if writing_skills else ""

    if research_posts:
        samples = "\n---\n".join([p["text"] for p in research_posts[:5]])
        research_section = f"""以下は今日Threadsで反応が取れていた投稿のサンプルです：

【リサーチした投稿サンプル】
{samples}

上記サンプルの「語り口・構成・リズム」を参考にしつつ、"""
    else:
        research_section = "あなたの知識と経験をもとに、"

    prompt = f"""あなたはSNSマーケターのコピーライターです。

{research_section}
このプロフィールの人物として自然なThreads投稿文を1つ作成してください。

【投稿者のプロフィール】
{PROFILE}

【今回の投稿スタイル】
{style}
{pdca_section}{skills_section}
条件：
- 140〜300文字
- 宣伝臭なし、価値・共感・ストーリー重視
- ハッシュタグなし
- 改行を効果的に使う
- コピペ感なし、本人が書いたような自然さ

投稿文だけ出力してください。"""

    return _call_claude(prompt)

def get_todays_keywords():
    """曜日ベースで3キーワードを選択（7日で21キーワードを網羅）"""
    weekday = datetime.now().weekday()  # 0=月 〜 6=日
    start = weekday * 3
    return KEYWORDS[start:start + 1]

def main(post_count=10):
    todays_keywords = get_todays_keywords()
    print("=" * 50)
    print(f"🔍 Threadsリサーチ開始 - {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    print(f"   本日のキーワード: {', '.join(todays_keywords)}")
    print(f"   生成本数: {post_count}本")
    print("=" * 50)

    all_posts = []

    for keyword in todays_keywords:
        posts = scrape_threads(keyword, max_posts=8)
        all_posts.extend(posts)
        print(f"  {keyword}: {len(posts)}件取得")

    print(f"\n合計 {len(all_posts)} 件収集\n")
    print(f"✍️ 投稿文を{post_count}本生成中...\n")

    generated = []

    for i in range(post_count):
        post_text = generate_post_from_research(all_posts, i)

        if post_text:
            post_type_info = POST_TYPES[i % len(POST_TYPES)]
            generated.append({
                "index": i + 1,
                "type": post_type_info["type"],
                "label": post_type_info["label"],
                "text": post_text
            })
            print(f"【投稿 {i+1}/{post_count} - {post_type_info['label']}】")
            print(post_text)
            print("-" * 40)

    # 保存（前日分をリセット）
    output = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "posts": generated,
        "posted": [],
        "log": []
    }
    with open("today_posts.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(generated)}本の投稿文を today_posts.json に保存しました")
    return generated

if __name__ == "__main__":
    main()
