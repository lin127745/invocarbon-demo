import csv
import io
import os
import re
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select

import factors
import llm
from db import Dataset, InvoiceLine, PowerBill, Session, init_db

MAX_LINES = 200
DEMO_DIR = Path(__file__).parent / "demo"
CSV_COLUMNS = ["發票號碼", "發票日期", "賣方名稱", "品名", "數量", "單位", "金額"]

app = FastAPI(title="發票碳帳 API")
init_db()


def parse_date(text: str) -> date:
    m = re.fullmatch(r"(\d{2,4})[-/.](\d{1,2})[-/.](\d{1,2})", text.strip())
    if not m:
        raise ValueError(f"日期格式錯誤：{text}")
    y, mo, d = (int(g) for g in m.groups())
    return date(y + 1911 if y < 1000 else y, mo, d)  # 3-digit years are ROC years


def decode_csv(raw: bytes) -> list[dict]:
    for enc in ("utf-8-sig", "cp950"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise HTTPException(400, "檔案編碼無法辨識，請存成 UTF-8 或 Big5 的 CSV")
    rows = list(csv.DictReader(io.StringIO(text)))
    missing = [c for c in CSV_COLUMNS if rows and c not in rows[0]]
    if not rows or missing:
        raise HTTPException(400, f"CSV 缺少欄位：{'、'.join(missing) or '沒有資料列'}")
    if len(rows) > MAX_LINES:
        raise HTTPException(400, f"Demo 版每次最多 {MAX_LINES} 筆，這個檔案有 {len(rows)} 筆")
    return rows


def get_dataset(s, dataset_id: str) -> Dataset:
    ds = s.get(Dataset, dataset_id)
    if ds is None:
        raise HTTPException(404, "找不到這份資料，請重新載入")
    return ds


@app.get("/api/config")
def config():
    client = llm.gemini_client()
    try:
        model = llm.model_name(client) if client else None
    except Exception as e:
        model = f"無法取得模型清單：{str(e)[:120]}"
    return {"llm": client is not None, "model": model, "max_lines": MAX_LINES}


@app.get("/api/factors")
def factor_table():
    return {"rows": factors.factor_table(), "version": factors.FACTOR_VERSION, "electricity_version": factors.ELECTRICITY_VERSION}


@app.get("/api/template.csv", response_class=PlainTextResponse)
def template():
    sample = "AB12345678,2025-03-05,示範加油站,超級柴油,100,L,3150\n"
    return PlainTextResponse("﻿" + ",".join(CSV_COLUMNS) + "\n" + sample, media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=invoice_template.csv"})


@app.post("/api/datasets/demo")
def create_demo():
    """Each visitor gets a private copy of the demo factory, pre-classified so no LLM call is made."""
    with Session.begin() as s:
        ds = Dataset(name="示範金屬加工廠（虛構資料）", is_demo=True, classify_method="詞庫（預先分類）")
        s.add(ds)
        s.flush()
        with open(DEMO_DIR / "invoices.csv", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                s.add(InvoiceLine(dataset_id=ds.id, invoice_no=r["發票號碼"], invoice_date=parse_date(r["發票日期"]),
                                  seller=r["賣方名稱"], item=r["品名"], qty=float(r["數量"]), unit=r["單位"],
                                  amount=float(r["金額"]), category=r["category"], confidence=float(r["confidence"]),
                                  confirmed=float(r["confidence"]) >= llm.REVIEW_THRESHOLD))
        with open(DEMO_DIR / "bills.csv", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                s.add(PowerBill(dataset_id=ds.id, meter_no=r["電號"], period_start=parse_date(r["起日"]),
                                period_end=parse_date(r["迄日"]), kwh=float(r["度數"]), source="示範資料"))
        return {"id": ds.id}


@app.post("/api/datasets/upload")
async def upload(file: UploadFile = File(...)):
    rows = decode_csv(await file.read())
    try:
        parsed = [(r, parse_date(r["發票日期"]), float(r["數量"]), float(r["金額"] or 0)) for r in rows]
    except ValueError as e:
        raise HTTPException(400, f"資料格式錯誤：{e}")
    try:
        results, method = llm.classify([r["品名"] for r in rows])
    except Exception as e:  # a failed or rate-limited LLM call should not lose the upload
        print("Gemini classify failed:", repr(e), flush=True)
        results, method = [llm.classify_keyword(r["品名"]) for r in rows], f"詞庫（Gemini 失敗：{str(e)[:150]}）"
    with Session.begin() as s:
        ds = Dataset(name=file.filename or "上傳資料", classify_method=method)
        s.add(ds)
        s.flush()
        for (r, d, qty, amount), (cat, conf) in zip(parsed, results):
            s.add(InvoiceLine(dataset_id=ds.id, invoice_no=r["發票號碼"], invoice_date=d, seller=r["賣方名稱"],
                              item=r["品名"], qty=qty, unit=r["單位"], amount=amount, category=cat, confidence=conf,
                              confirmed=conf >= llm.REVIEW_THRESHOLD))
        return {"id": ds.id, "count": len(rows), "method": method}


def line_dict(ln: InvoiceLine) -> dict:
    return {"id": ln.id, "invoice_no": ln.invoice_no, "date": ln.invoice_date.isoformat(), "seller": ln.seller,
            "item": ln.item, "qty": ln.qty, "unit": ln.unit, "amount": ln.amount, "category": ln.category,
            "category_label": factors.CATEGORIES[ln.category]["label"], "confidence": ln.confidence, "confirmed": ln.confirmed}


@app.get("/api/datasets/{dataset_id}")
def dataset(dataset_id: str):
    with Session() as s:
        ds = get_dataset(s, dataset_id)
        lines = s.scalars(select(InvoiceLine).where(InvoiceLine.dataset_id == ds.id).order_by(InvoiceLine.invoice_date, InvoiceLine.id)).all()
        bills = s.scalars(select(PowerBill).where(PowerBill.dataset_id == ds.id).order_by(PowerBill.period_start)).all()
        return {
            "id": ds.id, "name": ds.name, "is_demo": ds.is_demo, "method": ds.classify_method,
            "categories": [{"key": k, "label": v["label"]} for k, v in factors.CATEGORIES.items()],
            "lines": [line_dict(ln) for ln in lines],
            "bills": [{"id": b.id, "meter_no": b.meter_no, "period_start": b.period_start.isoformat(),
                       "period_end": b.period_end.isoformat(), "kwh": b.kwh, "source": b.source} for b in bills],
        }


class LineUpdate(BaseModel):
    category: str


@app.patch("/api/datasets/{dataset_id}/lines/{line_id}")
def update_line(dataset_id: str, line_id: int, body: LineUpdate):
    if body.category not in factors.CATEGORIES:
        raise HTTPException(400, "不認得的類別")
    with Session.begin() as s:
        ln = s.get(InvoiceLine, line_id)
        if ln is None or ln.dataset_id != dataset_id:
            raise HTTPException(404, "找不到這筆發票")
        if body.category != "none":
            try:
                factors.to_standard_qty(body.category, ln.qty, ln.unit)
            except ValueError as e:
                raise HTTPException(400, str(e))
        ln.category, ln.confirmed = body.category, True
        return line_dict(ln)


class BillIn(BaseModel):
    meter_no: str
    period_start: date
    period_end: date
    kwh: float
    source: str = "手動輸入"


@app.post("/api/datasets/{dataset_id}/bills")
def add_bill(dataset_id: str, body: BillIn):
    if body.kwh <= 0 or body.period_end < body.period_start:
        raise HTTPException(400, "度數需大於 0，且迄日不可早於起日")
    with Session.begin() as s:
        get_dataset(s, dataset_id)
        s.add(PowerBill(dataset_id=dataset_id, meter_no=body.meter_no, period_start=body.period_start,
                        period_end=body.period_end, kwh=body.kwh, source=body.source[:20]))
    return {"ok": True}


@app.delete("/api/datasets/{dataset_id}/bills/{bill_id}")
def delete_bill(dataset_id: str, bill_id: int):
    with Session.begin() as s:
        b = s.get(PowerBill, bill_id)
        if b is None or b.dataset_id != dataset_id:
            raise HTTPException(404, "找不到這張帳單")
        s.delete(b)
    return {"ok": True}


@app.post("/api/bills/read")
async def read_bill(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "圖片請小於 5MB")
    try:
        return llm.read_bill(data, file.content_type or "image/jpeg")
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        print("Gemini bill read failed:", repr(e), flush=True)
        raise HTTPException(502, f"讀圖失敗（{str(e)[:150]}），請手動輸入")


@app.get("/api/datasets/{dataset_id}/report")
def report(dataset_id: str):
    with Session() as s:
        ds = get_dataset(s, dataset_id)
        lines = s.scalars(select(InvoiceLine).where(InvoiceLine.dataset_id == ds.id, InvoiceLine.category != "none")).all()
        bills = s.scalars(select(PowerBill).where(PowerBill.dataset_id == ds.id).order_by(PowerBill.period_start)).all()
        pending = s.query(InvoiceLine).filter(InvoiceLine.dataset_id == ds.id, InvoiceLine.confirmed.is_(False)).count()

    entries = []
    for ln in lines:
        e = factors.emission(ln.category, ln.qty, ln.unit)
        entries.append({"scope": 1, "category": ln.category, "label": factors.CATEGORIES[ln.category]["label"],
                        "kg": e["kg_co2e"], "confirmed": ln.confirmed,
                        "evidence": {"type": "電子發票", "ref": ln.invoice_no, "date": ln.invoice_date.isoformat(),
                                     "party": ln.seller, "item": ln.item, "qty": f"{ln.qty:g} {ln.unit}",
                                     "steps": e["steps"], "source": e["source"], "note": e["note"]}})
    for b in bills:
        e = factors.electricity(b.kwh)
        entries.append({"scope": 2, "category": "electricity", "label": "外購電力（台電）", "kg": e["kg_co2e"], "confirmed": True,
                        "evidence": {"type": "電費單", "ref": b.meter_no, "date": f"{b.period_start} ~ {b.period_end}",
                                     "party": "台灣電力公司", "item": f"計費度數（{b.source}）", "qty": f"{b.kwh:,.0f} 度",
                                     "steps": e["steps"], "source": e["source"], "note": None}})

    by_cat: dict[str, dict] = {}
    for en in entries:
        c = by_cat.setdefault(en["category"], {"category": en["category"], "label": en["label"], "scope": en["scope"], "kg": 0.0, "count": 0})
        c["kg"] += en["kg"]
        c["count"] += 1
    scope1 = sum(e["kg"] for e in entries if e["scope"] == 1)
    scope2 = sum(e["kg"] for e in entries if e["scope"] == 2)
    return {"name": ds.name, "scope1_t": scope1 / 1000, "scope2_t": scope2 / 1000, "total_t": (scope1 + scope2) / 1000,
            "pending": pending, "by_category": sorted(by_cat.values(), key=lambda c: -c["kg"]),
            "entries": sorted(entries, key=lambda e: -e["kg"])}


static_dir = os.environ.get("STATIC_DIR")
if static_dir and Path(static_dir).is_dir():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
