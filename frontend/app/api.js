export async function api(path, options = {}) {
  const res = await fetch(`/api${path}`, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `伺服器回應 ${res.status}`);
  return body;
}

export const t = (kg) => (kg / 1000).toLocaleString("zh-TW", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
