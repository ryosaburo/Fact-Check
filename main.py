import os
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

# 環境変数の読み込み
API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
CX = os.environ.get("GOOGLE_SEARCH_CX")

app = FastAPI(
    title="Fact Check Tool",
    description="Google検索を行って証拠を収集するツールです",
    version="1.0.0"
)

class SearchRequest(BaseModel):
    query: str

class SearchResultItem(BaseModel):
    title: str
    link: str
    snippet: str

class SearchResponse(BaseModel):
    results: List[SearchResultItem]
    formatted_context: str

# --- 500エラー対策: トップページの設定 ---
@app.get("/")
def read_root():
    return {"status": "ok", "message": "Fact Check API is running"}

@app.post("/search", response_model=SearchResponse)
async def search_evidence(request: SearchRequest):
    # 1. APIキーの存在チェック
    if not API_KEY or not CX:
        return SearchResponse(results=[], formatted_context="エラー: Vercelの環境変数(APIキー/CX)が設定されていません。")

    search_url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": API_KEY,
        "cx": CX,
        "q": request.query,
        "lr": "lang_ja",
        "num": 5
    }

    try:
        # 2. Google APIへのリクエスト（タイムアウト設定を追加）
        response = requests.get(search_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        # エラーが起きても500を返さず、メッセージを返す
        return SearchResponse(results=[], formatted_context=f"検索中にエラーが発生しました: {str(e)}")

    items = data.get("items", [])
    if not items:
        return SearchResponse(results=[], formatted_context="関連する証拠が見つかりませんでした。")

    results_list = []
    context_parts = []
    for i, item in enumerate(items):
        title = item.get("title", "No Title")
        link = item.get("link", "")
        snippet = item.get("snippet", "").replace("\n", " ")
        
        results_list.append(SearchResultItem(title=title, link=link, snippet=snippet))
        context_parts.append(f"資料{i+1}: {title}\nURL: {link}\n内容: {snippet}\n---")

    return SearchResponse(
        results=results_list,
        formatted_context="\n".join(context_parts)
    )