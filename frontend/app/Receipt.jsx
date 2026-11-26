import { t } from "./api";

export default function Receipt({ entry }) {
  const ev = entry.evidence;
  return (
    <article className="receipt" aria-label="證據鏈">
      <h3>{ev.type}{ev.type === "電費單" ? "電號" : "號碼"}</h3>
      <div className="ref">{ev.ref}</div>
      <dl>
        <dt>日期</dt><dd>{ev.date}</dd>
        <dt>對象</dt><dd>{ev.party}</dd>
        <dt>品項</dt><dd>{ev.item}</dd>
        <dt>數量</dt><dd>{ev.qty}</dd>
        <dt>排放源</dt><dd>範疇{entry.scope === 1 ? "一" : "二"}｜{entry.label}</dd>
      </dl>
      <div className="cut" />
      <ol>{ev.steps.map((s) => <li key={s}>{s}</li>)}</ol>
      {ev.note && <p className="src">換算假設：{ev.note}</p>}
      <div className="result">{t(entry.kg)} 公噸 CO2e</div>
      <p className="src">係數依據：{ev.source}</p>
    </article>
  );
}
