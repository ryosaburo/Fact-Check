import os
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

# --- 設定 ---
# VercelのEnvironment Variablesで設定した名前と一致させてください
API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
CX = os.environ.get("GOOGLE_SEARCH_CX")

app = FastAPI(title="Fact Check Search Tool for Dify")

# --- データモデル定義 ---
class SearchRequest(BaseModel):
    query: str  # Difyから渡される検索クエリ

class SearchResultItem(BaseModel):
    title: str
    link: str
    snippet: str

class SearchResponse(BaseModel):
    results: List[SearchResultItem]
    formatted_context: str  # GPTにそのまま渡すための整形済みテキスト

# --- 信頼性評価（簡易版） ---
def evaluate_source(url: str) -> str:
    if any(domain in url for domain in [".go.jp", ".ac.jp", "cao.go.jp", "mhlw.go.jp"]):
        return "【信頼性：高（公的・学術機関）】"
    if any(domain in url for domain in ["asahi.com", "yomiuri.co.jp", "nikkei.com", "mainichi.jp", "nhk.or.jp"]):
        return "【信頼性：中（主要ニュースメディア）】"
    return "【信頼性：不明（一般サイト・SNS等）】"

# --- APIエンドポイント ---
@app.post("/search", response_model=SearchResponse)
async def search_evidence(request: SearchRequest):
    if not API_KEY or not CX:
        raise HTTPException(status_code=500, detail="APIキーまたはCXが設定されていません。")

    # Google Custom Search API へのリクエスト
    search_url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": API_KEY,
        "cx": CX,
        "q": request.query,
        "lr": "lang_ja", # 日本語の結果を優先
        "num": 5         # 取得件数（Dify/GPTのトークン制限を考慮し5件程度がおすすめ）
    }

    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google Search APIエラー: {str(e)}")

    items = data.get("items", [])
    results_list = []
    context_parts = []

    # 検索結果の整形
    for i, item in enumerate(items):
        title = item.get("title")
        link = item.get("link")
        snippet = item.get("snippet", "").replace("\n", " ")
        reliability = evaluate_source(link)

        results_list.append(SearchResultItem(title=title, link=link, snippet=snippet))
        
        # GPTが証拠として扱いやすいフォーマットを作成
        context_parts.append(
            f"資料{i+1}: {title}\n"
            f"URL: {link}\n"
            f"信頼性指標: {reliability}\n"
            f"内容要約: {snippet}\n"
            "---"
        )

    formatted_context = "\n".join(context_parts) if context_parts else "関連する証拠が見つかりませんでした。"

    return SearchResponse(
        results=results_list,
        formatted_context=formatted_context
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)