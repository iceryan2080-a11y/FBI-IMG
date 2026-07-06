export async function analyzeImage(file, mode) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("mode", mode);
  const res = await fetch("/api/analyze", { method: "POST", body: fd });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch { /* respuesta sin JSON */ }
    throw new Error(detail);
  }
  return res.json();
}
