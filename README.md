# 發票碳帳 Demo

用電子發票進項明細與台電電費單，自動產出可回查的範疇一、二碳盤查。IdeaX 創星季 2026 解方提案的概念驗證版本，所有示範資料皆為虛構。

## 架構

- 前端：Next.js（靜態輸出，由後端一併提供）
- 後端：FastAPI + SQLAlchemy
- 資料庫：PostgreSQL（跑在同一個容器內，重啟後清空）
- 發票品名分類、電費單讀圖：Google Gemini；未設定金鑰時改用關鍵字詞庫與手動輸入

## 係數來源

- 燃料燃燒與 GWP（AR5）：環境部 113 年 2 月 5 日公告「溫室氣體排放係數」
- 電力：能源署 114 年度電力排碳係數 0.467 kg CO2e/度
- 燃料熱值暫採 IPCC 2006 預設值，正式版改用能源署公告熱值；乙炔以質量平衡估算

## 部署（Render 免費版）

在 Render 建立 Web Service，來源選這個儲存庫，Language 選 Docker，Instance Type 選 Free。環境變數：

- `GEMINI_API_KEY`：Google AI Studio 金鑰；不設定也能運作
- `GEMINI_MODEL`（選填）：預設 `gemini-2.5-flash`

## 本機開發

```
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest
cd ../frontend && npm install && npx next build
cd ../backend && .venv/Scripts/python run_local.py   # http://127.0.0.1:8765
```
