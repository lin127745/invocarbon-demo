"""Generates the fictional demo factory data (run once; output is committed)."""
import csv
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from llm import classify_keyword

random.seed(7)
OUT = Path(__file__).parent / "demo"
FONT = "C:/Windows/Fonts/msjh.ttc"


def inv_no():
    return random.choice(["AB", "CD", "EF", "GH", "JK", "MN"]) + f"{random.randint(0, 99999999):08d}"


rows = []
for m in range(1, 13):
    d = lambda day: f"2025-{m:02d}-{day:02d}"
    rows.append([inv_no(), d(5), "順發加油站", "超級柴油（堆高機用）", 100, "L", 3050])
    rows.append([inv_no(), d(8), "大明瓦斯行", "工業用液化石油氣", 2, "桶", 1700])
    rows.append([inv_no(), d(12), "金泰鋼材", "SS400 鋼板 6mm", random.randint(20, 40), "片", random.randint(60000, 120000)])
    rows.append([inv_no(), d(15), "永信工業用品", random.choice(["耐磨手套", "砂輪片 4 吋", "焊條 E7016", "切削油 18L"]), random.randint(5, 50), "個", random.randint(1500, 9000)])
    rows.append([inv_no(), d(20), "光明文具", random.choice(["A4 影印紙", "碳粉匣", "文具一批"]), random.randint(1, 10), "箱", random.randint(800, 4000)])
    if m % 3 == 0:
        rows.append([inv_no(), d(18), "永信氣體行", "乙炔 7kg 鋼瓶灌充", 6, "kg", 2400])
    if m % 2 == 0:
        rows.append([inv_no(), d(22), "協和螺絲", "六角螺絲 M10", random.randint(500, 2000), "支", random.randint(2000, 6000)])
rows.append([inv_no(), "2025-07-10", "冷氣工程行", "R-410A 冷媒補充", 10, "kg", 8500])
rows.append([inv_no(), "2025-08-14", "冷氣工程行", "R-32 冷媒補充", 3, "kg", 2700])
rows.append([inv_no(), "2025-04-02", "順發加油站", "發電機用柴油", 200, "L", 6100])
rows.append([inv_no(), "2025-09-09", "永信氣體行", "工業用氣體一批", 12, "kg", 3600])
rows.append([inv_no(), "2025-10-21", "宏達機械", "車床保養", 1, "式", 15000])
rows.sort(key=lambda r: r[1])

OUT.mkdir(exist_ok=True)
with open(OUT / "invoices.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["發票號碼", "發票日期", "賣方名稱", "品名", "數量", "單位", "金額", "category", "confidence"])
    for r in rows:
        cat, conf = classify_keyword(r[3])
        w.writerow(r + [cat, conf])

kwh = [38200, 36100, 39800, 40100, 41900, 44200, 45800, 45100, 42300, 38900, 34600, 33000]  # 480,000 in total
with open(OUT / "bills.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["電號", "起日", "迄日", "度數"])
    for m, k in enumerate(kwh, start=1):
        end = f"2025-{m + 1:02d}-04" if m < 12 else "2026-01-04"
        w.writerow(["07-12-3456-78-9", f"2025-{m:02d}-05", end, k])

# A sample bill photo for trying the OCR step; plainly marked as not a real bill.
img = Image.new("RGB", (900, 620), "#fbf8f1")
g = ImageDraw.Draw(img)
big, mid, small = (ImageFont.truetype(FONT, s) for s in (40, 28, 22))
g.rectangle([20, 20, 880, 600], outline="#333", width=3)
g.text((40, 40), "電費通知單（示範用，非真實帳單）", font=big, fill="#111")
lines = [("用戶名稱", "示範金屬加工廠"), ("電號", "07-12-3456-78-9"), ("計費期間", "115/02/05 至 115/03/04"),
         ("本期指數", "1,284,600"), ("上期指數", "1,243,350"), ("本期計費度數", "41,250 度"), ("應繳總金額", "NT$ 198,450 元")]
for i, (k, v) in enumerate(lines):
    y = 120 + i * 60
    g.text((60, y), k, font=mid, fill="#444")
    g.text((330, y), v, font=mid, fill="#111")
    g.line([50, y + 48, 850, y + 48], fill="#ccc")
g.text((60, 560), "本圖由發票碳帳 Demo 產生，資料皆為虛構", font=small, fill="#888")
img.save(OUT / "sample_bill.png")
print(len(rows), "invoice lines;", sum(kwh), "kWh")
