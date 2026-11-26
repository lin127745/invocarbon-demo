"use client";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, t } from "../api";
import Receipt from "../Receipt";

export default function Page() {
  return (
    <Suspense fallback={<main className="wrap">載入中…</main>}>
      <Workspace />
    </Suspense>
  );
}

function Workspace() {
  const id = useSearchParams().get("id");
  const [data, setData] = useState(null);
  const [report, setReport] = useState(null);
  const [tab, setTab] = useState("lines");
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    try {
      const [d, r] = await Promise.all([api(`/datasets/${id}`), api(`/datasets/${id}/report`)]);
      setData(d);
      setReport(r);
    } catch (e) {
      setError(e.message);
    }
  }, [id]);
  useEffect(() => { if (id) reload(); }, [id, reload]);

  if (!id || error) return <main className="wrap"><p className="error">{error || "缺少資料代號"}</p><a href="/">回首頁重新開始</a></main>;
  if (!data) return <main className="wrap">載入中…</main>;

  return (
    <main className="wrap">
      <div className="ws-head">
        <h1>{data.name}</h1>
        <span className="fine">品名分類方式：{data.method}</span>
      </div>
      <div className="steps" role="tablist">
        <button role="tab" aria-selected={tab === "lines"} onClick={() => setTab("lines")}>
          1 確認發票{report.pending > 0 && <span className="count">{report.pending} 筆待確認</span>}
        </button>
        <button role="tab" aria-selected={tab === "bills"} onClick={() => setTab("bills")}>2 電費單</button>
        <button role="tab" aria-selected={tab === "report"} onClick={() => setTab("report")}>3 盤查報表</button>
      </div>
      {tab === "lines" && <Lines id={id} data={data} onChange={reload} />}
      {tab === "bills" && <Bills id={id} bills={data.bills} onChange={reload} />}
      {tab === "report" && <Report report={report} />}
    </main>
  );
}

function Lines({ id, data, onChange }) {
  const [filter, setFilter] = useState("sources");
  const [msg, setMsg] = useState("");
  const shown = data.lines
    .filter((l) => (filter === "all" ? true : filter === "review" ? !l.confirmed : l.category !== "none" || !l.confirmed))
    .sort((a, b) => a.confirmed - b.confirmed);

  async function change(line, category) {
    setMsg("");
    try {
      await api(`/datasets/${id}/lines/${line.id}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ category }),
      });
      onChange();
    } catch (e) {
      setMsg(e.message);
    }
  }

  return (
    <>
      <div className="toolbar">
        <label>顯示
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="sources">排放源與待確認</option>
            <option value="review">只看待確認</option>
            <option value="all">全部 {data.lines.length} 筆</option>
          </select>
        </label>
        <span className="fine">黃底是系統沒把握的項目，選好類別就算確認。</span>
      </div>
      {msg && <p className="error" role="alert">{msg}</p>}
      <div className="scroll">
        <table className="grid">
          <thead><tr><th>日期</th><th className="hide-sm">發票號碼</th><th className="hide-sm">賣方</th><th>品名</th><th className="num">數量</th><th>排放源類別</th></tr></thead>
          <tbody>
            {shown.map((l) => (
              <tr key={l.id} className={l.confirmed ? "" : "review"}>
                <td>{l.date.slice(5)}</td>
                <td className="hide-sm">{l.invoice_no}</td>
                <td className="hide-sm">{l.seller}</td>
                <td className="item">{l.item}</td>
                <td className="num">{l.qty.toLocaleString()} {l.unit}</td>
                <td>
                  <select aria-label={`${l.item} 的類別`} value={l.category} onChange={(e) => change(l, e.target.value)}>
                    {data.categories.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
                  </select>
                  {!l.confirmed && <> <span className="badge warn">待確認</span></>}
                  {l.confirmed && !l.category.startsWith("none") && l.confidence < 0.8 && <> <span className="badge">已確認</span></>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Bills({ id, bills, onChange }) {
  const empty = { meter_no: "", period_start: "", period_end: "", kwh: "" };
  const [form, setForm] = useState(empty);
  const [source, setSource] = useState("手動輸入");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  async function read(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";
    setBusy(true);
    setStatus("正在讀取帳單…");
    const body = new FormData();
    body.append("file", file);
    try {
      const r = await api("/bills/read", { method: "POST", body });
      setForm({ meter_no: r.meter_no || "", period_start: r.period_start || "", period_end: r.period_end || "", kwh: r.kwh ?? "" });
      setSource("讀圖");
      setStatus("讀到了，請核對下面的欄位再加入。");
    } catch (err) {
      setStatus(`${err.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function add(e) {
    e.preventDefault();
    try {
      await api(`/datasets/${id}/bills`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, kwh: Number(form.kwh), source }),
      });
      setForm(empty);
      setSource("手動輸入");
      setStatus("已加入電費單。");
      onChange();
    } catch (err) {
      setStatus(err.message);
    }
  }

  async function remove(b) {
    await api(`/datasets/${id}/bills/${b.id}`, { method: "DELETE" });
    onChange();
  }

  const field = (k, label, type = "text") => (
    <label>{label}<input required type={type} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} /></label>
  );

  return (
    <>
      <section className="panel">
        <h2>新增電費單</h2>
        <div className="actions" style={{ marginBottom: 14 }}>
          <label className="btn ghost small">
            {busy ? "讀取中…" : "上傳帳單照片"}
            <input type="file" accept="image/*" hidden disabled={busy} onChange={read} />
          </label>
          <a href="/sample_bill.png" download>下載示範帳單圖片</a>
        </div>
        {status && <p className="fine" role="status">{status}</p>}
        <form className="form" onSubmit={add}>
          {field("meter_no", "電號")}
          {field("period_start", "計費起日", "date")}
          {field("period_end", "計費迄日", "date")}
          {field("kwh", "計費度數", "number")}
          <button className="btn small" type="submit">加入</button>
        </form>
      </section>
      <div className="scroll">
        <table className="grid">
          <thead><tr><th>電號</th><th>計費期間</th><th className="num">度數</th><th className="hide-sm">來源</th><th /></tr></thead>
          <tbody>
            {bills.map((b) => (
              <tr key={b.id}>
                <td>{b.meter_no}</td>
                <td>{b.period_start} ~ {b.period_end}</td>
                <td className="num">{b.kwh.toLocaleString()}</td>
                <td className="hide-sm"><span className="badge">{b.source}</span></td>
                <td><button className="btn ghost small" onClick={() => remove(b)}>刪除</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Report({ report }) {
  const [open, setOpen] = useState(null);
  const [factors, setFactors] = useState(null);
  useEffect(() => { api("/factors").then(setFactors).catch(() => {}); }, []);
  const max = Math.max(...report.by_category.map((c) => c.kg), 1);

  return (
    <>
      {report.pending > 0 && <p className="notice">還有 {report.pending} 筆發票待確認，下面的數字尚未包含這些項目的最終判斷。</p>}
      <div className="totals">
        <div><b>{report.scope1_t.toLocaleString("zh-TW", { maximumFractionDigits: 2 })}</b><span>範疇一（公噸 CO2e）</span></div>
        <div><b>{report.scope2_t.toLocaleString("zh-TW", { maximumFractionDigits: 2 })}</b><span>範疇二（公噸 CO2e）</span></div>
        <div><b>{report.total_t.toLocaleString("zh-TW", { maximumFractionDigits: 2 })}</b><span>合計（公噸 CO2e）</span></div>
      </div>
      <div className="bars" aria-label="各排放源排放量">
        {report.by_category.map((c) => (
          <div key={c.category} className={`bar s${c.scope}`}>
            <span>{c.label}</span>
            <div className="track"><div className="fill" style={{ width: `${(c.kg / max) * 100}%` }} /></div>
            <span className="v">{t(c.kg)} 噸</span>
          </div>
        ))}
      </div>
      <p className="fine">點任一列，看這筆排放量是從哪張單據、怎麼算出來的。</p>
      <div className="scroll">
        <table className="grid">
          <thead><tr><th>範疇</th><th>排放源</th><th>來源單據</th><th className="hide-sm">日期</th><th className="num">公噸 CO2e</th></tr></thead>
          <tbody>
            {report.entries.map((e, i) => (
              <tr key={i} className="click" tabIndex={0} onClick={() => setOpen(e)} onKeyDown={(k) => k.key === "Enter" && setOpen(e)}>
                <td>{e.scope === 1 ? "一" : "二"}</td>
                <td>{e.label}{!e.confirmed && <> <span className="badge warn">待確認</span></>}</td>
                <td>{e.evidence.type} {e.evidence.ref}</td>
                <td className="hide-sm">{e.evidence.date}</td>
                <td className="num">{t(e.kg)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {factors && (
        <section className="panel" style={{ marginTop: 28 }}>
          <h2>使用的係數</h2>
          <div className="scroll">
            <table className="grid">
              <tbody>
                {factors.rows.map((r) => (
                  <tr key={r.category}><td>{r.label}</td><td className="num">{r.per_unit.toLocaleString()}</td><td>{r.unit}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="fine">{factors.version}；{factors.electricity_version}。燃料熱值暫採 IPCC 2006 預設值，正式版改用能源署公告熱值；乙炔以質量平衡估算。</p>
        </section>
      )}
      {open && (
        <>
          <div className="drawer-back" onClick={() => setOpen(null)} />
          <aside className="drawer" role="dialog" aria-label="證據鏈">
            <button className="btn ghost small close" onClick={() => setOpen(null)} autoFocus>關閉</button>
            <h2 style={{ color: "var(--green)", marginTop: 0 }}>證據鏈</h2>
            <Receipt entry={open} />
          </aside>
        </>
      )}
    </>
  );
}
