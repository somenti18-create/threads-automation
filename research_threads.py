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

            # 参考投稿サンプルを取得
            ref_posts = data.get("reference_posts", [])
            samples_text = ""
            if ref_posts:
                samples = []
                for ref in ref_posts:
                    account = ref.get("account", "")
                    note = ref.get("note", "")
                    for s in ref.get("samples", []):
                        samples.append(f"[{account} / {note}]\n{s}")
                if samples:
                    samples_text = "\n\n【参考アカウントの実際の投稿（文体・構成・リズムをトレースすること）】\n" + "\n---\n".join(samples)

            result = ""
            if target:
                result += f"【ターゲット】{target}\n\n"
            result += f"【ルール】\n{rules_text}"
            result += samples_text
            return result
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
    {
        "type": "viral",
        "label": "フック型",
        "description": """冒頭に「えっ？」となる強い一言を置く。
例）「SNSを毎日100投稿してたのに反応なし。」「フォロワー1000人いるのに予約0。」
→ 正直な感情（やめたくなった・意味ないと思った）
→ でも続けてた・続けてる
→ 最後は「〜な人いますか？」または「〜って思ってる人いませんか？」
80〜130文字・1文10文字以下・改行多め"""
    },
    {
        "type": "connect",
        "label": "繋がり投稿",
        "description": "「整体・サロン・パーソナルトレーナーでSNSや集客に悩んでる方と繋がりたい！」形式。箇条書き3つ以内。最後は「繋がりましょう！！」。80〜130文字"
    },
    {
        "type": "viral",
        "label": "逆説型",
        "description": """「〇〇してるのに〇〇」という逆説を冒頭に置く。
例）「毎日投稿してるのに予約が増えない。」「LINEを導入したのに来店に繋がらない。」
→ 自分もそうだった・周りもそう
→ 気づいたこと・変わったこと（説明しない、感情だけ）
→ 最後は問いかけ
80〜130文字・1文10文字以下・改行多め"""
    },
    {
        "type": "viral",
        "label": "告白型",
        "description": """「正直に言うと〜」「ぶっちゃけ〜」から始める。
本音・弱音・迷い・葛藤を短く語る。
例）「正直、SNSが嫌いになりかけてた。」「ぶっちゃけ何回もやめようと思った。」
→ でも続けた理由・気づき
→ 最後は断定か軽い問いかけ
80〜130文字・1文10文字以下・改行多め"""
    },
    {
        "type": "connect",
        "label": "繋がり投稿",
        "description": "「整体・サロン・パーソナルトレーナーでSNSや集客に悩んでる方と繋がりたい！」形式。箇条書き3つ以内。最後は「繋がりましょう！！」。80〜130文字"
    },
    {
        "type": "viral",
        "label": "問題提起型",
        "description": """「〇〇って意味ないな」「〇〇は間違いだった」など、一般的な常識や努力を疑う一言から始める。
例）「SNSってあんまり意味ないな、って思ってた。」
→ そう思ってた理由・状況
→ でも実は〜だった（結論は出さなくていい、問いかけでOK）
→ 最後は「〜って思ってる人いませんか？」
80〜130文字・1文10文字以下・改行多め"""
    },
]

# 2日に1回差し込む「元公務員ストーリー」タイプ
POST_TYPE_STORY = {"type": "viral", "label": "ストーリー投稿", "description": """以下の実体験エピソードからどれか1つをテーマに、感情ベースで短く語る。
エピソード候補：
- 公務員を辞めた
- 転売をやっていた
- 動画編集をやっていた
- いろんな副業を転々としていた
- 結局たどり着いたのが起業

構成：短い事実の積み重ね（1文1行）→最後は「結局〜した/なった。」など断定で終わる。問いかけなし。説明・宣伝ゼロ。80〜130文字・1文10文字以下・改行多め"""}

PROFILE = """
名前: 小野寺壮史 / POLYNK (@line_polynk)
ビジネス:
- 個人事業主・小規模店舗向けSNS運用代行（LINE / Threads / Instagram / YouTube / TikTok）
- 業務効率化・自動化代行（Claude Codeでシステム構築）
  → LINE自動化・Threads自動投稿・請求書自動作成・予約管理・在庫管理など雑務全般
差別化: SNSのフォロワー数ではなく「売上に直結する導線設計」にフォーカス
実績:
- 整体・パーソナルトレーナー・せどりスクール・全国6店舗飲食を支援
- 月商70万→700万
- 売上5000万規模のLINE運用
支援内容: SNS運用代行（Instagram/Threads/YouTube/TikTok/LINE）・業務の仕組み化
対応エリア: 全国オンライン対応
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

def generate_post_from_research(research_posts, post_index, post_type_override=None):
    """リサーチ結果を元にClaudeで投稿文を生成"""
    post_type_info = post_type_override if post_type_override else POST_TYPES[post_index % len(POST_TYPES)]
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

def main(post_count=3):
    print("=" * 50)
    print(f"✍️ 投稿文生成開始 - {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    print(f"   生成本数: {post_count}本（リサーチなし・writing_skills+PDCA基準）")
    print("=" * 50)

    all_posts = []  # リサーチなし

    print(f"\n✍️ 投稿文を{post_count}本生成中...\n")

    generated = []

    # 偶数日は1本目をストーリー投稿に差し替え
    use_story_today = (datetime.now().day % 2 == 0)

    for i in range(post_count):
        if i == 0 and use_story_today:
            post_type_info = POST_TYPE_STORY
        else:
            post_type_info = POST_TYPES[i % len(POST_TYPES)]

        post_text = generate_post_from_research(all_posts, i, post_type_override=post_type_info if (i == 0 and use_story_today) else None)

        if post_text:
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
