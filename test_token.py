import requests
import os
from dotenv import dotenv_values

config = dotenv_values(".env")
token = config["THREADS_ACCESS_TOKEN"]

# ユーザー情報取得テスト
url = "https://graph.threads.net/v1.0/me"
params = {
    "fields": "id,username,name",
    "access_token": token
}

response = requests.get(url, params=params)
print("ステータスコード:", response.status_code)
print("レスポンス:", response.json())
