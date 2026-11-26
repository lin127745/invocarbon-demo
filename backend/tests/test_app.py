import pytest

import factors
from llm import classify_keyword


def test_diesel_per_litre_matches_hand_calculation():
    # 1 L x 0.84 kg/L x 43.0 TJ/Gg = 3.612e-5 TJ; (74100 + 3.9x30 + 3.9x265) kg/TJ x 3.612e-5 TJ
    expected = 0.84 / 1e6 * 43.0 * (74100 + 3.9 * 30 + 3.9 * 265)
    assert factors.emission("diesel_mobile", 1, "L")["kg_co2e"] == pytest.approx(expected)
    assert expected == pytest.approx(2.718, abs=0.001)


def test_lpg_cylinders_convert_to_kg():
    e = factors.emission("lpg", 2, "桶")
    assert e["std_qty"] == 40
    assert "20 公斤" in e["note"]


def test_litres_cannot_be_used_for_refrigerant():
    with pytest.raises(ValueError):
        factors.emission("r410a", 5, "L")


def test_electricity_uses_published_factor():
    assert factors.electricity(480_000)["kg_co2e"] == pytest.approx(224_160)


@pytest.mark.parametrize("item,cat", [("超級柴油（堆高機用）", "diesel_mobile"), ("發電機用柴油", "diesel_stationary"),
                                      ("R-410A 冷媒補充", "r410a"), ("工業用液化石油氣", "lpg"), ("切削油 18L", "none")])
def test_keyword_classification(item, cat):
    assert classify_keyword(item)[0] == cat


def test_vague_item_needs_review():
    assert classify_keyword("工業用氣體一批")[1] < 0.8


def test_demo_flow_report_and_review(client):
    ds_id = client.post("/api/datasets/demo").json()["id"]
    data = client.get(f"/api/datasets/{ds_id}").json()
    assert len(data["lines"]) == 75 and len(data["bills"]) == 12

    rep = client.get(f"/api/datasets/{ds_id}/report").json()
    assert rep["scope2_t"] == pytest.approx(224.16)
    assert rep["pending"] == 1

    vague = next(ln for ln in data["lines"] if ln["item"] == "工業用氣體一批")
    r = client.patch(f"/api/datasets/{ds_id}/lines/{vague['id']}", json={"category": "acetylene"})
    assert r.status_code == 200
    rep2 = client.get(f"/api/datasets/{ds_id}/report").json()
    assert rep2["pending"] == 0
    assert rep2["scope1_t"] == pytest.approx(rep["scope1_t"] + 12 * factors.ACETYLENE_KG_CO2_PER_KG / 1000)

    top = rep2["entries"][0]
    assert top["evidence"]["ref"] and top["evidence"]["steps"]


def test_demo_copies_are_independent(client):
    a = client.post("/api/datasets/demo").json()["id"]
    b = client.post("/api/datasets/demo").json()["id"]
    diesel = next(ln for ln in client.get(f"/api/datasets/{a}").json()["lines"] if ln["category"] == "diesel_mobile")
    client.patch(f"/api/datasets/{a}/lines/{diesel['id']}", json={"category": "none"})
    assert client.get(f"/api/datasets/{a}/report").json()["scope1_t"] < client.get(f"/api/datasets/{b}/report").json()["scope1_t"]


def test_upload_csv_with_roc_dates_and_big5(client):
    csv_text = "發票號碼,發票日期,賣方名稱,品名,數量,單位,金額\nAB00000001,114/03/05,順發加油站,高級柴油,50,公升,1500\nAB00000002,114/03/06,光明文具,A4 影印紙,2,箱,600\n"
    r = client.post("/api/datasets/upload", files={"file": ("x.csv", csv_text.encode("cp950"), "text/csv")})
    assert r.status_code == 200, r.text
    lines = client.get(f"/api/datasets/{r.json()['id']}").json()["lines"]
    assert lines[0]["date"] == "2025-03-05" and lines[0]["category"] == "diesel_mobile"


def test_upload_rejects_missing_columns(client):
    r = client.post("/api/datasets/upload", files={"file": ("x.csv", "品名,數量\n柴油,1\n".encode(), "text/csv")})
    assert r.status_code == 400


def test_manual_bill_and_validation(client):
    ds_id = client.post("/api/datasets/demo").json()["id"]
    bad = client.post(f"/api/datasets/{ds_id}/bills", json={"meter_no": "x", "period_start": "2025-02-01", "period_end": "2025-01-01", "kwh": 10})
    assert bad.status_code == 400
    ok = client.post(f"/api/datasets/{ds_id}/bills", json={"meter_no": "07-12-3456-78-9", "period_start": "2026-01-05", "period_end": "2026-02-04", "kwh": 1000})
    assert ok.status_code == 200
    assert client.get(f"/api/datasets/{ds_id}/report").json()["scope2_t"] == pytest.approx(224.16 + 0.467)


def test_bill_reading_without_key_asks_for_manual_entry(client):
    r = client.post("/api/bills/read", files={"file": ("b.png", b"\x89PNG", "image/png")})
    assert r.status_code == 503
