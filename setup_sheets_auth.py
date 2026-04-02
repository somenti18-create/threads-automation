"""
Googleスプレッドシート認証セットアップ（ローカルで一度だけ実行）
実行するとブラウザが開くのでGoogleアカウントでログイン → 許可
→ token.json が生成されます
→ その内容をRenderの環境変数 GOOGLE_TOKEN_JSON に貼る
"""

from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path
import json

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file"
]
CREDS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE  = Path(__file__).parent / "token_sheets.json"

print("ブラウザが開きます。Googleアカウントでログインして許可してください...\n")
flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
creds = flow.run_local_server(port=0)
TOKEN_FILE.write_text(creds.to_json())

print(f"\n✅ 認証成功！ {TOKEN_FILE} を生成しました")
print("\n" + "="*60)
print("以下をコピーしてRenderの環境変数 GOOGLE_TOKEN_JSON に貼ってください：")
print("="*60)
print(TOKEN_FILE.read_text())
