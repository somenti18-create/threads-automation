import json
import os
import anthropic
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

PROFILE = """
名前: 小野寺壮史 / POLYNK
アカウント: @line_polynk
ビジネス概要:
- SNS運用代行（YouTube / TikTok / LINE / Threads）
- 業務効率化・自動化代行（Claude Codeでシステム構築）
  → 請求書作成・シフト管理・Google MEO・Threads自動化など
差別化: SNSの数値ではなく「売上向上」にフォーカス
実績: YouTubeとLINE運用で月商70万→700万（10倍以上）
名前の由来: POLY（多数）＝複数のSNS×複数のアプローチで企業の売上を上げる
ターゲット: 飲食店・スクール・中小企業のオーナー・担当者
"""

POST_TEMPLATES = [
    "実績・ビフォーアフターのストーリー型",
    "SNSマーケティングの知識・ノウハウ提供型",
    "共感型（SNS担当者・経営者あるある）",
    "業務効率化の事例・Claudeでできること紹介型",
    "POLYNKの想い・価値観・差別化を語る型",
]

def generate_post(template):
    prompt = f"""あなたはSNSマーケターのコピーライターです。
以下のプロフィールの人物として、Threadsに投稿する文章を1つ作成してください。

【プロフィール】
{PROFILE}

【投稿スタイル】
- {template}
- 140〜300文字程度
- 改行を効果的に使う
- ハッシュタグは使わない
- 宣伝臭をなくし、価値や共感を優先
- 読んだ人が「いいね」や「返信」したくなる文章
- 語尾はです・ます調でも、フランクでもOK（自然に）

投稿文だけを出力してください。前置きや説明は不要です。"""

    return _call_claude(prompt)

def generate_posts():
    posts = []

    for template in POST_TEMPLATES:
        print(f"\n生成中: {template}...")
        post_text = generate_post(template)
        posts.append({
            "template": template,
            "text": post_text
        })
        print(f"\n【{template}】")
        print(post_text)
        print("-" * 40)

    with open("generated_posts.json", "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

    print("\n✅ 投稿文を generated_posts.json に保存しました")
    return posts

if __name__ == "__main__":
    generate_posts()
