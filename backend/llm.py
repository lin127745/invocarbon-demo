"""Invoice item classification (keyword dictionary, or Gemini when a key is set) and bill reading."""
import json
import os
import re

from factors import CATEGORIES

_model = os.environ.get("GEMINI_MODEL")  # unset: picked from the models this key can use
SKIP = ("lite", "image", "tts", "live", "audio", "embedding", "exp")
REVIEW_THRESHOLD = 0.8

# Order matters: the first matching pattern wins.
KEYWORDS = [
    (r"r-?410a", "r410a"), (r"r-?134a", "r134a"), (r"r-?32\b", "r32"),
    (r"乙炔", "acetylene"),
    (r"液化石油氣|lpg|桶裝瓦斯|丙烷", "lpg"),
    (r"發電機.*柴油|鍋爐.*柴油", "diesel_stationary"),
    (r"柴油", "diesel_mobile"),
    (r"9[25]\s*無鉛|98\s*無鉛|汽油", "gasoline_mobile"),
]
# Words that suggest a possible emission source the dictionary cannot pin down.
VAGUE = re.compile(r"氣體|燃料|冷媒|瓦斯|油料")


def gemini_client():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    from google import genai
    return genai.Client(api_key=key)


def pick_flash_model(names: list[str]) -> str | None:
    """Newest general-purpose flash model; stable releases beat previews of the same version."""
    def key(n):
        m = re.search(r"gemini-(\d+(?:\.\d+)?)", n)
        return (float(m.group(1)) if m else 0, "preview" not in n)
    cands = [n for n in names if "flash" in n and not any(x in n for x in SKIP)]
    return max(cands, key=key) if cands else None


def model_name(client) -> str:
    global _model
    if _model is None:
        names = [m.name.removeprefix("models/") for m in client.models.list()
                 if "generateContent" in (getattr(m, "supported_actions", None) or [])]
        _model = pick_flash_model(names) or "gemini-flash-latest"
    return _model


def classify_keyword(item: str) -> tuple[str, float]:
    text = item.lower()
    for pattern, cat in KEYWORDS:
        if re.search(pattern, text):
            return cat, 0.9
    if VAGUE.search(item):
        return "none", 0.4
    return "none", 0.95


PROMPT = """你是台灣製造業溫室氣體盤查助理。以下是工廠電子發票進項的品名，請判斷每一項屬於哪個排放源類別。
類別代碼與說明：
{cats}
規則：
- 只有實際會被燃燒或逸散的燃料、氣體、冷媒才算排放源；設備、耗材、潤滑油、切削油都是 none。
- 柴油若用於堆高機、貨車等移動設備選 diesel_mobile，用於發電機、鍋爐選 diesel_stationary，無法判斷時選 diesel_mobile 並降低信心。
- confidence 介於 0 到 1，無法確定時給 0.6 以下。
只輸出 JSON 陣列，每個元素為 {{"i": 序號, "category": 類別代碼, "confidence": 數字}}。
品名清單：
{items}"""


def classify(items: list[str]) -> tuple[list[tuple[str, float]], str]:
    """Returns (category, confidence) per item and the method used."""
    client = gemini_client()
    if client is None:
        return [classify_keyword(i) for i in items], "詞庫"
    cats = "\n".join(f"- {k}: {v['label']}" for k, v in CATEGORIES.items())
    listing = "\n".join(f"{n}. {t}" for n, t in enumerate(items))
    model = model_name(client)
    resp = client.models.generate_content(
        model=model,
        contents=PROMPT.format(cats=cats, items=listing),
        config={"response_mime_type": "application/json", "temperature": 0},
    )
    out = [classify_keyword(i) for i in items]
    for row in json.loads(resp.text):
        i, cat = int(row["i"]), row["category"]
        if 0 <= i < len(items) and cat in CATEGORIES:
            out[i] = (cat, float(row["confidence"]))
    return out, f"Gemini（{model}）"


BILL_PROMPT = """這是一張台灣電費帳單的照片。請讀出以下欄位，只輸出 JSON：
{"meter_no": "電號", "period_start": "計費起日 YYYY-MM-DD", "period_end": "計費迄日 YYYY-MM-DD", "kwh": 本期計費度數（數字）}
民國年請換算成西元年。讀不到的欄位填 null。"""


def read_bill(image: bytes, mime: str) -> dict:
    client = gemini_client()
    if client is None:
        raise RuntimeError("未設定 Gemini 金鑰，請手動輸入帳單資料")
    from google.genai import types
    resp = client.models.generate_content(
        model=model_name(client),
        contents=[types.Part.from_bytes(data=image, mime_type=mime), BILL_PROMPT],
        config={"response_mime_type": "application/json", "temperature": 0},
    )
    return json.loads(resp.text)
