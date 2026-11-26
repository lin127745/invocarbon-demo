"use client";
import { useRef, useState } from "react";
import { api } from "./api";
import Receipt from "./Receipt";

const SAMPLE = {
  scope: 2, label: "外購電力（台電）", kg: 19263.75,
  evidence: {
    type: "電費單", ref: "07-12-3456-78-9", date: "2026-02-05 ~ 2026-03-04", party: "台灣電力公司",
    item: "計費度數", qty: "41,250 度", steps: ["41,250 度 × 0.467 kg CO2e/度"], source: "能源署 114 年度電力排碳係數",
  },
};

export default function Home() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef(null);

  async function start(promise) {
    setBusy(true);
    setError("");
    try {
      const { id } = await promise;
      window.location.href = `/workspace/?id=${id}`;
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }

  function upload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    start(api("/datasets/upload", { method: "POST", body: form }));
    e.target.value = "";
  }

  return (
    <main className="wrap">
      <section className="hero">
        <div>
          <h1>把發票和電費單，直接變成碳盤查</h1>
          <p>
            匯入電子發票進項明細和台電電費單，系統會找出柴油、液化石油氣、冷媒等排放源，套用環境部和能源署公告的係數，
            算出範疇一、二排放量。每一筆數字都對得到原始單據。
          </p>
          <div className="actions">
            <button className="btn" disabled={busy} onClick={() => start(api("/datasets/demo", { method: "POST" }))}>
              {busy ? "載入中…" : "看示範工廠"}
            </button>
            <button className="btn ghost" disabled={busy} onClick={() => fileRef.current.click()}>上傳發票 CSV</button>
            <input ref={fileRef} type="file" accept=".csv,text/csv" hidden onChange={upload} />
            <a href="/api/template.csv">下載 CSV 範本</a>
          </div>
          {error && <p className="error" role="alert">{error}</p>}
          <p className="fine">
            示範工廠是虛構的金屬加工廠，含一年份 75 筆發票與 12 張電費單。上傳的檔案會送到 Google Gemini 分類，請勿上傳真實營業資料。
          </p>
        </div>
        <Receipt entry={SAMPLE} />
      </section>
      <ol className="flow">
        <li><b>1 匯入單據</b><span>電子發票進項明細、電費單照片</span></li>
        <li><b>2 認出排放源</b><span>讀發票品名，不確定的交給你確認</span></li>
        <li><b>3 套官方係數</b><span>環境部排放係數、能源署電力係數</span></li>
        <li><b>4 產出盤查表</b><span>每筆排放量都能點開看來源</span></li>
      </ol>
    </main>
  );
}
