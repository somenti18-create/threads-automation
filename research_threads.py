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

            # フックパターン
            hook_data = data.get("hook_patterns", {})
            hook_text = ""
            if hook_data:
                hook_desc = hook_data.get("description", "")
                patterns = hook_data.get("patterns", [])
                pattern_lines = "\n".join([
                    f"・{p['label']}：{p['example'].split(chr(10))[0]}　→　{p['note']}"
                    for p in patterns
                ])
                hook_text = f"\n\n【冒頭フックパターン（毎回違うパターンを使うこと）】\n{hook_desc}\n{pattern_lines}"

            # コンテンツトピック
            topics_data = data.get("content_topics", {})
            topics_text = ""
            if topics_data:
                topics_desc = topics_data.get("description", "")
                topics = topics_data.get("topics", [])
                topic_lines = "\n".join([f"・{t['label']}：{t['description'][:60]}…" for t in topics])
                topics_text = f"\n\n【話題のバリエーション（導線の話ばかりにしない）】\n{topics_desc}\n{topic_lines}"

            result = ""
            if target:
                result += f"【ターゲット】{target}\n\n"
            result += f"【ルール】\n{rules_text}"
            result += pain_text
            result += hook_text
            result += topics_text
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

# 時間帯固定の投稿タイプ（5投稿/日）
# UTC: ["01:00","04:00","08:00","10:00","12:00"]
# JST: [ 10:00,  13:00,  17:00,  19:00,  21:00]
POST_TYPES_BY_SLOT = [
    {   # JST 10:00 実体験型
        "type": "viral", "label": "実体験型",
        "topic_hint": "自動化・仕組み化 / SNS数字との向き合い方 / リピーターを作る話 からランダムに選ぶ",
        "hook_hint": "落差型（数字の対比）か体験の入口型（相談・会話から始める）",
        "description": """自分が実際にやった仕事の話を一人称で語る。
冒頭2行：落差型（「フォロワー1,200人、予約0件。」）か体験入口型（「先週〇〇さんからこんな相談が来た。」）で始める。
→ 何をやったか → どうなったか（具体的な数字） → 気づき
押しつけNG。自分の体験を淡々と共有するスタンス。80〜200文字"""
    },
    {   # JST 13:00 事例型
        "type": "viral", "label": "事例型",
        "topic_hint": "値上げの話 / 選ばれる理由を作る話 / リピーターを作る話 からランダムに選ぶ",
        "hook_hint": "数字で始める型（「月商70万が、3ヶ月後に700万になった。」）",
        "description": """実際に支援したクライアントの事例を語る。売り込みNG。
冒頭2行：数字で始める型（「月商70万が3ヶ月で700万になった。やったことは〇〇じゃなかった。」）で引きを作る。
「あるサロンさん」「あるスクールのオーナーさん」など。
テーマ例：「値上げしたら客が増えた」「フォロワー増やすより選ばれる理由を作った」「リピーターが増えて新規集客不要になった」
→ 相談内容（数字・状況） → 何を変えたか → 変化後の事実（数字）
「〜したんじゃなくて〜しただけ」のような気づきで締める。80〜200文字"""
    },
    {   # JST 17:00 本音・失敗
        "type": "viral", "label": "本音型",
        "topic_hint": "SNS信頼構築の話 / 自動化失敗の話 / 起業の葛藤 からランダムに選ぶ",
        "hook_hint": "逆張り型か落差型。「正直〜」「ぶっちゃけ〜」も有効",
        "description": """正直な本音・失敗・葛藤を語る。
冒頭2行：「正直、フォロワーが増えても全然嬉しくなかった。」「自動化した3日後にシステムが止まった。」など失敗・本音から入る。
テーマ例：「フォロワー増えても売上変わらなくて焦った」「自動化が壊れて手作業に戻った話」「信頼を積むには時間がかかるという話」
→ 状況 → 正直な感情 → でも気づいたこと
共感を押しつけない。「〜なんですよね」で自然に締める。80〜200文字"""
    },
    {   # JST 19:00 繋がり
        "type": "connect", "label": "繋がり投稿",
        "hook_hint": "ターゲット直撃型（「整体師さんへ。」）か数字で始める型",
        "description": """整体・サロン・パーソナルトレーナーでSNSや集客に悩んでる方に向けた繋がり投稿。
冒頭2行：「整体師さんへ。」「サロンオーナーさんに聞いてほしい話。」など職種を直撃するか、「月商70万→700万になった方を支援しています。」など実績から入る。
毎回違うパターンで：問いかけ型・宣言型・共感型をローテーション。
自分の仕事内容・支援実績にさらっと触れてから繋がりを誘う。
締めは「気軽にお話しましょう！」か「お話聞くだけでも全然大丈夫です！」80〜200文字"""
    },
    {   # JST 21:00 ストーリー型
        "type": "viral", "label": "ストーリー型",
        "hook_hint": "落差型か本音から入る。公務員→副業転々→起業の流れ",
        "description": """元公務員→副業転々→起業という自分のキャリアストーリーを語る。
冒頭2行：「公務員を辞めた理由は、給料が安かったからじゃない。」「転売で月3万稼いだとき、会社員の30万より重かった。」など落差や本音から入る。
毎回違うエピソードを選ぶ：公務員時代・転売の失敗・動画編集の経験・起業を決めた瞬間・最初のクライアント獲得。
→ 当時の状況（一人称） → 感情・葛藤 → どうなったか
「結局〜だった。」など断定で終わる。80〜200文字"""
    },
]

# 後方互換用（3postsモードなど）
POST_TYPES = POST_TYPES_BY_SLOT

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

def generate_post_from_research(research_posts, post_index, post_type_override=None, hypothesis=None, use_skills=True):
    """リサーチ結果を元にClaudeで投稿文を生成
    use_skills=True  → writing_skills.json + PDCA指示あり（A variant）
    use_skills=False → プロフィール＋スタイル指示のみ（B variant / Claude生素）
    """
    post_type_info = post_type_override if post_type_override else POST_TYPES[post_index % len(POST_TYPES)]
    style = f"【{post_type_info['label']}】{post_type_info['description']}"

    # PDCAからの最新指示を取得（仮説はmainで取得済みのものを使う）
    pdca_instructions_raw, _ = get_pdca_instructions()
    # 仮説セクションを別途構築
    hyp_section = ""
    if hypothesis:
        hyp_section = f"\n\n【今回検証する仮説】\n{hypothesis['content']}\n（この仮説を意識した投稿を作ること）"
    pdca_instructions = pdca_instructions_raw + hyp_section if pdca_instructions_raw else hyp_section

    if use_skills:
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
    else:
        # skills なし：PDCAもスキルも渡さない（Claudeの素の判断で生成）
        pdca_section = ""
        skills_section = ""

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
- 文字数は80〜200文字（厳守。超えたら書き直し）
- 改行を効果的に使う（読みやすさ重視）
- ハッシュタグなし・宣伝臭なし
- 語尾タメ口NG：「〜しない？」「〜じゃない？」「〜かもしれない」「〜だと思う」
- 語尾OK：「〜なんですよね」「〜かもしれません」「〜だったりします」「〜な人いませんか？」「〜な人いるんじゃないかな」
- 小野寺さん自身が主語（一人称で語る）
- 実際にあった仕事・体験・実験・失敗をベースに書く（架空の話NG）
- 具体的な数字を入れる（時間・金額・倍率など）
- 読者に押しつけない。気づきを共有するスタンス

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

    # 時間帯スロット順に生成（10投稿=全スロット順・3投稿=先頭3スロット）
    # A/Bテスト: 奇数スロット(1,3,5,7,9本目)=skillsあり / 偶数スロット(2,4,6,8,10本目)=skillsなし
    for i in range(post_count):
        post_type_info = POST_TYPES_BY_SLOT[i % len(POST_TYPES_BY_SLOT)]
        use_skills = (i % 2 == 0)  # 0-indexed: 0,2,4,6,8 → skills / 1,3,5,7,9 → no_skills
        variant = "skills" if use_skills else "no_skills"

        post_text, used_hypothesis = generate_post_from_research(
            all_posts, i, post_type_override=post_type_info,
            hypothesis=current_hypothesis, use_skills=use_skills
        )

        if post_text:
            entry = {
                "index": i + 1,
                "type": post_type_info["type"],
                "label": post_type_info["label"],
                "variant": variant,
                "text": post_text
            }
            if used_hypothesis:
                entry["hypothesis_id"] = used_hypothesis["id"]
            generated.append(entry)
            print(f"【投稿 {i+1}/{post_count} - {post_type_info['label']} [{variant}]】")
            print(post_text)
            print("-" * 40)

    # 前日分をyesterday_posts.jsonに退避（朝レポート用）
    try:
        with open("today_posts.json", "r", encoding="utf-8") as f:
            prev = json.load(f)
        if prev.get("log"):  # 投稿済みデータがある場合のみ退避
            with open("yesterday_posts.json", "w", encoding="utf-8") as f:
                json.dump(prev, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

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
