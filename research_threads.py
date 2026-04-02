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
        from pdca_engine import get_current_instructions, get_hypothesis_to_test
        instructions = get_current_instructions()
        hyp = get_hypothesis_to_test()
        if hyp:
            instructions += f"\n\n【今回検証する仮説】\n{hyp['content']}\n（この仮説を意識した投稿を作ること）"
        return instructions, hyp
    except:
        return "", None

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

            pain_points = data.get("persona_pain_points", [])
            pain_text = ""
            if pain_points:
                pain_text = "\n\n【ターゲットが抱えているリアルな悩み（必ずどれか1つを投稿の核にすること）】\n" + "\n".join([f"・{p}" for p in pain_points])

            result = ""
            if target:
                result += f"【ターゲット】{target}\n\n"
            result += f"【ルール】\n{rules_text}"
            result += pain_text
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
        "description": """冒頭に強い一言を置く。
例）「フォロワーが1000人もいるのに予約が0。」
→ 深刻な感情（やめようかと思った・廃業が頭をよぎった）
→ でも続けてた理由・気づき
→ 最後は「〜な人いるんじゃないかな」か断定
50〜110文字・改行多め"""
    },
    {
        "type": "connect",
        "label": "繋がり投稿（箇条書き型）",
        "description": """「整体・サロン・パーソナルトレーナーでSNSや集客に悩んでる方と繋がりたいんですよね」形式。
ペルソナの悩みから3つ箇条書き。締めは「困ってる人も繋がりましょう！お話聞くだけでも全然大丈夫です！」
50〜110文字"""
    },
    {
        "type": "viral",
        "label": "逆説型",
        "description": """「〇〇してるのに〇〇」という逆説を冒頭に置く。
例）「フォロワーが100人も増えたのに予約が0。」
→「どうしても」「なのに」「それでも」で深刻さを強調
→ 原因は「見せ方」が違っただけ
→ 最後は「〜な人いませんか？」か断定
50〜110文字・改行多め"""
    },
    {
        "type": "viral",
        "label": "告白型",
        "description": """「正直お店を辞めようかと思った」レベルの深刻な本音から始める。
施術・店舗経営で体ボロボロ、寝る時間削ってSNS、でも売上0、を短く積み重ねる。
→ 原因は「見せ方」が少し違っただけだった
→ 断定か自然な余韻で終わる
50〜110文字・改行多め"""
    },
    {
        "type": "connect",
        "label": "繋がり投稿（問いかけ型）",
        "description": """冒頭にペルソナの悩みを問いかけ形式で置く。
例）「フォロワーは増えてるのに予約が入らない経験ってありませんか？」
→ 自分もそうだった・同じ悩みを持つ人と話したい
→ 締めは「困ってる人も繋がりましょう！お話聞くだけでも全然大丈夫です！」
50〜110文字・改行多め"""
    },
    {
        "type": "viral",
        "label": "問題提起型",
        "description": """「〇〇って意味ないな」「〇〇は間違いだった」と一般的な努力を疑う一言から始める。
→ そう思ってた理由・状況（数字は出てるのに売上0など）
→ でも見せ方を変えたら違った
→ 最後は「〜な人いるんじゃないかな」か「〜な人いませんか？」
50〜110文字・改行多め"""
    },
    {
        "type": "connect",
        "label": "繋がり投稿（宣言型）",
        "description": """「整体・サロン・トレーナーの方の見せ方を変えるのを手伝いたいと思ってます」という宣言から始める。
→ なぜそう思うか（自分も同じ悩みを経験した・技術があるのに伝わらないのはもったいない）
→ 締めは「困ってる人も繋がりましょう！お話聞くだけでも全然大丈夫です！」
50〜110文字・改行多め"""
    },
    {
        "type": "viral",
        "label": "フック型",
        "description": """冒頭に強い数字や事実を置く。
例）「毎日投稿して3ヶ月。売上は0のまま。」
→ その時の感情（虚しかった・誰にも言えなかった）
→ 気づき・変化
→ 最後は「〜な人いませんか？」か断定
50〜110文字・改行多め"""
    },
    {
        "type": "dm",
        "label": "DM誘導型",
        "description": """ペルソナの悩みに深く共感してから「話を聞きたい」でDMに誘導する。
→ 冒頭：ペルソナが抱えてる深刻な悩みを1〜2行で代弁
→ 中盤：「そういう方の話をもっと聞きたいと思ってます」
→ 締め：「気軽にご連絡ください！」で終わる（これ以外NG）
押し売りゼロ。あくまで「聞きたい」スタンス。
50〜110文字・改行多め"""
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

構成：短い事実の積み重ね（1文1行）→最後は「結局〜した/なった。」など断定で終わる。問いかけなし。説明・宣伝ゼロ。50〜110文字・改行多め"""}

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

def generate_post_from_research(research_posts, post_index, post_type_override=None, hypothesis=None):
    """リサーチ結果を元にClaudeで投稿文を生成"""
    post_type_info = post_type_override if post_type_override else POST_TYPES[post_index % len(POST_TYPES)]
    style = f"【{post_type_info['label']}】{post_type_info['description']}"

    # PDCAからの最新指示を取得（仮説はmainで取得済みのものを使う）
    pdca_instructions_raw, _ = get_pdca_instructions()
    # 仮説セクションを別途構築
    hyp_section = ""
    if hypothesis:
        hyp_section = f"\n\n【今回検証する仮説】\n{hypothesis['content']}\n（この仮説を意識した投稿を作ること）"
    pdca_instructions = pdca_instructions_raw + hyp_section if pdca_instructions_raw else hyp_section
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

    prompt = f"""あなたはSNSコピーライターです。

{research_section}
このプロフィールの人物として自然なThreads投稿文を1つ作成してください。

【投稿者のプロフィール】
{PROFILE}

【今回の投稿スタイル】
{style}
{pdca_section}{skills_section}
【絶対に守る条件】
- 文字数は50〜110文字（厳守。超えたら書き直し）
- 1文は10文字以下。短く切る
- 改行は1〜2行ごと
- 説明しない。感情と事実だけ
- ハッシュタグなし・宣伝臭なし
- 語尾タメ口NG：「〜しない？」「〜じゃない？」「〜かもしれない」「〜だと思う」
- 語尾OK：「〜なんですよね」「〜かもしれません」「〜だったりします」「〜な人いませんか？」「〜な人いるんじゃないかな」

投稿文だけ出力してください。"""

    post_text = _call_claude(prompt)
    return post_text, hypothesis

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

    # 今回検証する仮説を取得
    _, current_hypothesis = get_pdca_instructions()
    if current_hypothesis:
        print(f"\n🧪 検証仮説: {current_hypothesis['content'][:60]}")

    print(f"\n✍️ 投稿文を{post_count}本生成中...\n")

    generated = []

    # 日付ベースでPOST_TYPESをずらして毎日違うタイプを生成
    day_offset = datetime.now().day % len(POST_TYPES)

    for i in range(post_count):
        post_type_info = POST_TYPES[(day_offset + i) % len(POST_TYPES)]
        post_text, used_hypothesis = generate_post_from_research(
            all_posts, i, post_type_override=post_type_info, hypothesis=current_hypothesis
        )

        if post_text:
            entry = {
                "index": i + 1,
                "type": post_type_info["type"],
                "label": post_type_info["label"],
                "text": post_text
            }
            if used_hypothesis:
                entry["hypothesis_id"] = used_hypothesis["id"]
            generated.append(entry)
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
