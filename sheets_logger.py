"""
Googleスプレッドシートへのデータ書き込みモジュール
- インサイト履歴
- PDCA履歴
- フォロワー推移
"""

import os
import json
import gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from datetime import datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file"
]

SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")


def _get_client():
    """認証済みgspreadクライアントを返す（Render環境変数から）"""
    token_json = os.environ.get("GOOGLE_TOKEN_JSON", "")
    if not token_json:
        raise ValueError("GOOGLE_TOKEN_JSON 環境変数が未設定です")

    token_data = json.loads(token_json)
    creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return gspread.authorize(creds)


def _get_or_create_sheet(spreadsheet, title, headers):
    """シート（タブ）を取得または作成してヘッダーを設定"""
    try:
        ws = spreadsheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=1000, cols=len(headers))
        ws.append_row(headers)
    return ws


def log_insight(record: dict):
    """インサイト1件をスプレッドシートに追記"""
    if not SHEET_ID:
        return

    try:
        gc = _get_client()
        sh = gc.open_by_key(SHEET_ID)

        headers = [
            "計測日時", "投稿ID", "投稿テキスト", "投稿タイプ", "文字数",
            "投稿日時(JST)", "JST時", "曜日", "経過時間(h)",
            "views", "likes", "replies", "reposts", "quotes", "shares", "clicks",
            "variant", "hypothesis_id"
        ]
        ws = _get_or_create_sheet(sh, "インサイト履歴", headers)

        row = [
            record.get("measured_at", ""),
            record.get("post_id", ""),
            record.get("post_text", ""),
            record.get("post_type", ""),
            record.get("post_char_count", 0),
            record.get("posted_at", ""),
            record.get("jst_hour", ""),
            record.get("weekday", ""),
            record.get("hours", 0),
            record.get("views", 0),
            record.get("likes", 0),
            record.get("replies", 0),
            record.get("reposts", 0),
            record.get("quotes", 0),
            record.get("shares", 0),
            record.get("clicks", 0),
            record.get("variant", ""),
            record.get("hypothesis_id", ""),
        ]
        ws.append_row(row)
        print(f"📊 スプシ書き込み: {record.get('post_text','')[:20]}... {record.get('hours')}h後")

    except Exception as e:
        print(f"⚠️ スプシ書き込みエラー: {e}")


def log_pdca(analysis_text: str, hypothesis: str, top_score: int):
    """PDCA分析結果をスプレッドシートに追記"""
    if not SHEET_ID:
        return

    try:
        gc = _get_client()
        sh = gc.open_by_key(SHEET_ID)

        headers = ["日付", "仮説サマリー", "トップスコア", "分析全文"]
        ws = _get_or_create_sheet(sh, "PDCA履歴", headers)

        row = [
            datetime.now().strftime("%Y-%m-%d"),
            hypothesis,
            top_score,
            analysis_text[:5000],  # Sheetsセルの文字数上限対策
        ]
        ws.append_row(row)

    except Exception as e:
        print(f"⚠️ PDCA書き込みエラー: {e}")


def log_follower(count: int):
    """フォロワー数をスプレッドシートに追記"""
    if not SHEET_ID:
        return

    try:
        gc = _get_client()
        sh = gc.open_by_key(SHEET_ID)

        headers = ["日付", "フォロワー数"]
        ws = _get_or_create_sheet(sh, "フォロワー推移", headers)
        ws.append_row([datetime.now().strftime("%Y-%m-%d"), count])

    except Exception as e:
        print(f"⚠️ フォロワー書き込みエラー: {e}")
