"""Emission factors and the per-line emission calculation.

Combustion factors (kg/TJ) and GWP (AR5) come from 環境部 113-02-05 公告「溫室氣體排放係數」
(環部授氣字第1139101231號), 附表一 and the GWP table. That notice gives factors per TJ, so a
heat value is needed to get per-litre / per-kg figures; the official 能源署 heat values could not
be verified, so IPCC 2006 default net calorific values are used and flagged in the output.
"""

FACTOR_VERSION = "環境部 113.02.05 公告溫室氣體排放係數（GWP 採 AR5）"
ELECTRICITY_VERSION = "能源署 114 年度電力排碳係數"
ELECTRICITY_KG_PER_KWH = 0.467

GWP = {"CO2": 1, "CH4_fossil": 30, "N2O": 265}
# R-410A is a 50/50 blend of HFC-32 (677) and HFC-125 (3,170).
REFRIGERANT_GWP = {"r410a": 1923.5, "r32": 677, "r134a": 1300}

# kg/TJ from 附表一; ncv in TJ per Gg (IPCC 2006 Vol.2 Table 1.2); density in kg per litre.
COMBUSTION = {
    "diesel_mobile": {"label": "柴油（移動源，如堆高機、貨車）", "unit": "L", "co2": 74100, "ch4": 3.9, "n2o": 3.9, "ncv": 43.0, "density": 0.84},
    "diesel_stationary": {"label": "柴油（固定源，如發電機、鍋爐）", "unit": "L", "co2": 74100, "ch4": 3, "n2o": 0.6, "ncv": 43.0, "density": 0.84},
    "gasoline_mobile": {"label": "車用汽油（移動源）", "unit": "L", "co2": 69300, "ch4": 3.8, "n2o": 5.7, "ncv": 44.3, "density": 0.74},
    "lpg": {"label": "液化石油氣（固定源）", "unit": "kg", "co2": 63100, "ch4": 1, "n2o": 0.1, "ncv": 47.3, "density": None},
}
# Acetylene is not in the notice: C2H2 + 2.5 O2 -> 2 CO2, so 2 x 44.01 / 26.04 kg CO2 per kg.
ACETYLENE_KG_CO2_PER_KG = round(2 * 44.01 / 26.04, 3)

CATEGORIES = {
    **{k: {"label": v["label"], "scope": 1, "unit": v["unit"]} for k, v in COMBUSTION.items()},
    "acetylene": {"label": "乙炔（焊切割，估算）", "scope": 1, "unit": "kg"},
    "r410a": {"label": "冷媒 R-410A（逸散）", "scope": 1, "unit": "kg"},
    "r32": {"label": "冷媒 R-32（逸散）", "scope": 1, "unit": "kg"},
    "r134a": {"label": "冷媒 R-134a（逸散）", "scope": 1, "unit": "kg"},
    "none": {"label": "非排放源", "scope": None, "unit": None},
}

# Units accepted per category and how they convert to the standard unit.
UNIT_ALIASES = {"l": "L", "公升": "L", "升": "L", "kg": "kg", "公斤": "kg", "千克": "kg"}
CYLINDER_KG = {"lpg": 20}  # one 桶 of bottled LPG is assumed to be 20 kg


def to_standard_qty(category: str, qty: float, unit: str) -> tuple[float, str | None]:
    """Returns the quantity in the category's standard unit and a note on any assumption made."""
    std = CATEGORIES[category]["unit"]
    u = UNIT_ALIASES.get(unit.strip().lower(), unit.strip())
    if u == std:
        return qty, None
    if u == "桶" and category in CYLINDER_KG:
        return qty * CYLINDER_KG[category], f"1 桶以 {CYLINDER_KG[category]} 公斤計"
    if std == "kg" and u == "L" or std == "L" and u == "kg":
        raise ValueError(f"單位 {unit} 無法換算成 {std}")
    raise ValueError(f"不認得的單位：{unit}")


def emission(category: str, qty: float, unit: str) -> dict:
    """kg CO2e for one invoice line, with every step needed to show the evidence chain."""
    std_qty, note = to_standard_qty(category, qty, unit)
    steps = []
    if category in COMBUSTION:
        f = COMBUSTION[category]
        mass_kg = std_qty * f["density"] if f["unit"] == "L" else std_qty
        tj = mass_kg / 1e6 * f["ncv"]
        co2, ch4, n2o = tj * f["co2"], tj * f["ch4"], tj * f["n2o"]
        kg = co2 + ch4 * GWP["CH4_fossil"] + n2o * GWP["N2O"]
        if f["unit"] == "L":
            steps.append(f"{std_qty:,.1f} L × 密度 {f['density']} kg/L = {mass_kg:,.1f} kg")
        steps.append(f"{mass_kg:,.1f} kg × 熱值 {f['ncv']} TJ/Gg = {tj:.5f} TJ")
        steps.append(f"CO2 {f['co2']:,} + CH4 {f['ch4']}×{GWP['CH4_fossil']} + N2O {f['n2o']}×{GWP['N2O']} kg/TJ")
        source = FACTOR_VERSION + "；熱值暫採 IPCC 2006 預設值，正式版改用能源署公告熱值"
    elif category == "acetylene":
        kg = std_qty * ACETYLENE_KG_CO2_PER_KG
        steps.append(f"{std_qty:,.1f} kg × {ACETYLENE_KG_CO2_PER_KG} kg CO2/kg（C2H2 完全燃燒質量平衡）")
        source = "公告未列乙炔燃燒係數，以質量平衡估算"
    elif category in REFRIGERANT_GWP:
        kg = std_qty * REFRIGERANT_GWP[category]
        steps.append(f"補充量 {std_qty:,.1f} kg 視為逸散量 × GWP {REFRIGERANT_GWP[category]:,}")
        source = FACTOR_VERSION + "；以年度補充量估算逸散量"
    else:
        return {"kg_co2e": 0.0, "std_qty": std_qty, "steps": [], "source": None, "note": note}
    return {"kg_co2e": kg, "std_qty": std_qty, "steps": steps, "source": source, "note": note}


def electricity(kwh: float) -> dict:
    kg = kwh * ELECTRICITY_KG_PER_KWH
    return {"kg_co2e": kg, "steps": [f"{kwh:,.0f} 度 × {ELECTRICITY_KG_PER_KWH} kg CO2e/度"], "source": ELECTRICITY_VERSION}


def factor_table() -> list[dict]:
    rows = []
    for key, f in COMBUSTION.items():
        per_unit = emission(key, 1, f["unit"])["kg_co2e"]
        rows.append({"category": key, "label": f["label"], "per_unit": round(per_unit, 4), "unit": f"kg CO2e/{f['unit']}"})
    rows.append({"category": "acetylene", "label": CATEGORIES["acetylene"]["label"], "per_unit": ACETYLENE_KG_CO2_PER_KG, "unit": "kg CO2/kg"})
    for key, g in REFRIGERANT_GWP.items():
        rows.append({"category": key, "label": CATEGORIES[key]["label"], "per_unit": g, "unit": "kg CO2e/kg（GWP）"})
    rows.append({"category": "electricity", "label": "外購電力（台電）", "per_unit": ELECTRICITY_KG_PER_KWH, "unit": "kg CO2e/度"})
    return rows
